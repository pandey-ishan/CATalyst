"""Recording thread and bounded background local OCR pipeline."""
from __future__ import annotations
import ctypes
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import mss
import numpy as np
from PySide6.QtCore import QThread, Signal
from .parser import ocr_lines, parse_test_provider
from .choice_marks import apply_choice_marks, readable_option_frame
from .math_ocr import restore_superscripts


class CaptureWorker(QThread):
    observation = Signal(object)
    status = Signal(str)
    failure = Signal(str)

    def __init__(self, region: dict, directory: Path, keep_screenshots: bool):
        super().__init__()
        self.region = region
        self.directory = directory
        self.keep_screenshots = keep_screenshots
        self._lock = threading.Lock()
        self._paused = False
        self._stopped = False
        self._generation = 0
        self._engine = None

    def pause(self, paused: bool):
        with self._lock:
            self._paused = paused
            self._generation += 1  # discard in-flight OCR across pause/resume

    def stop(self):
        with self._lock:
            self._stopped = True

    def state(self):
        with self._lock:
            return self._stopped, self._paused, self._generation

    def _ocr(self, frame):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
        ocr_frame = readable_option_frame(frame)
        result, _ = self._engine(ocr_frame)
        lines = ocr_lines(result)
        lines, math_warnings, original_math = restore_superscripts(ocr_frame, lines, self._engine)
        question = parse_test_provider(lines, frame.shape[1], frame.shape[0])
        if question is None:
            # Small counters can disappear at normal scale. Re-read just the
            # header locally, preserving its original coordinates and checks.
            h,w=frame.shape[:2]
            crop=ocr_frame[:max(1,int(h*.24)),:max(1,int(w*.5))]
            retry,_=self._engine(cv2.resize(crop,None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC))
            from .parser import Line
            enlarged=[Line(l.text,l.x/3,l.y/3,l.right/3,l.bottom/3,l.confidence) for l in ocr_lines(retry) if re.fullmatch(r'[0-9Il/|\s]+',l.text)]
            question=parse_test_provider(enlarged+lines,w,h)

        if question is not None:
            apply_choice_marks(question, lines, frame)
            question.warnings.extend(math_warnings)
            if original_math:
                question.raw_text += '\n\nOriginal OCR before exponent recovery:\n' + '\n'.join(original_math)
        return question

    @staticmethod
    def own_window_active():
        if os.name != 'nt':
            return False
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(process_id))
        return process_id.value == os.getpid()

    def run(self):
        writer = None
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='local-ocr')
        pending = None
        pending_frame = None
        pending_generation = -1
        last_small = None
        stable = 0
        processed = None
        last_generation = -1
        index = time.time_ns()
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            video = self.directory / f'recording-{time.time_ns()}.avi'
            width = self.region['width'] // 2 * 2
            height = self.region['height'] // 2 * 2
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 2.0, (width, height))
            if not writer.isOpened():
                raise RuntimeError('Could not create the local recording file')
            self.status.emit('Recording ready. Browse test provider with the question number visible.')
            with mss.mss() as screen:
                while True:
                    started = time.monotonic()
                    stopped, paused, generation = self.state()
                    if stopped:
                        # Finish OCR of the last pre-stop frame, but never revive paused work.
                        if pending is not None and not paused and generation == pending_generation:
                            question = pending.result()
                            if question is not None:
                                if self.keep_screenshots:
                                    name = f'q{question.number}-{index}.png'
                                    if not cv2.imwrite(str(self.directory / name), pending_frame):
                                        raise RuntimeError('Could not save optional screenshot')
                                    question.screenshots.append(name)
                                self.observation.emit((generation, question))
                        break
                    if generation != last_generation:
                        last_small = processed = None
                        stable = 0
                        last_generation = generation
                    if pending is not None and pending.done():
                        question = pending.result()
                        if not paused and generation == pending_generation:
                            if question is not None:
                                if self.keep_screenshots:
                                    name = f'q{question.number}-{index}.png'
                                    if not cv2.imwrite(str(self.directory / name), pending_frame):
                                        raise RuntimeError('Could not save optional screenshot')
                                    question.screenshots.append(name)
                                self.observation.emit((generation, question))
                                self.status.emit(f'Captured Q{question.number}: ' + (', '.join(question.views) or 'question text'))
                            else:
                                self.status.emit('Waiting for a visible question number (for example 01/22).')
                        pending = pending_frame = None
                    if paused:
                        self.msleep(100)
                        continue
                    if self.own_window_active():
                        last_small = processed = None
                        stable = 0
                        self.msleep(150)
                        continue
                    # Lock spans acquisition and recording: after pause returns, no new frame is written.
                    with self._lock:
                        if self._paused or self._stopped:
                            continue
                        frame = np.asarray(screen.grab(self.region))[:, :, :3].copy()[:height, :width]
                        writer.write(frame)
                    small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 100))
                    delta = np.mean(cv2.absdiff(small, last_small)) if last_small is not None else 255
                    stable = stable + 1 if delta < 1.3 else 0
                    last_small = small
                    changed = processed is None or np.mean(cv2.absdiff(small, processed)) > 1.3
                    if stable >= 1 and changed and pending is None:
                        pending_frame = frame
                        pending_generation = generation
                        pending = executor.submit(self._ocr, frame)
                        processed = small.copy()
                        index += 1
                        self.status.emit('Reading visible content locally...')
                    remaining = .5 - (time.monotonic() - started)
                    if remaining > 0:
                        self.msleep(int(remaining * 1000))
        except Exception as error:
            self.failure.emit(f'{type(error).__name__}: {error}')
        finally:
            if writer is not None:
                writer.release()
            executor.shutdown(wait=True, cancel_futures=True)
