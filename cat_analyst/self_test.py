"""Frozen-build smoke check; uses synthetic data and never opens user storage."""
import json
import os
from pathlib import Path

def run(report):
    try:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6.QtWidgets import QApplication
        from rapidocr_onnxruntime import RapidOCR
        import numpy as np
        import cv2
        from unittest.mock import patch
        import socket
        from .reader import QuestionReader
        from .core import Question
        app = QApplication.instance() or QApplication([])
        reader = QuestionReader([('Build check', Question(number=1, text='What is 2 + 2?'))])
        reader.show()
        app.processEvents()
        assert reader.browser.viewport().height() > 100
        reader.close()
        frame = np.full((180, 600, 3), 255, dtype=np.uint8)
        cv2.putText(frame, 'Question 14', (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,0,0), 3)
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')):
            engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
            result, _ = engine(frame)
        assert result and any('14' in row[1] for row in result), repr(result)
        Path(report).write_text(json.dumps({'ok': True, 'ocr': [row[1] for row in result], 'reader_height': reader.height()}))
    except Exception:
        import traceback
        Path(report).write_text(traceback.format_exc())
        raise
