from multiprocessing import freeze_support

if __name__ == '__main__':
    freeze_support()
    import sys
    if '--self-test' in sys.argv:
        from cat_analyst.self_test import run
        run(sys.argv[sys.argv.index('--self-test') + 1])
    else:
        from cat_analyst.ui import run
        run()
