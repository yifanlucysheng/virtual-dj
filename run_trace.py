import faulthandler
faulthandler.dump_traceback_later(20, exit=True)
exec(compile(open('main.py').read(), 'main.py', 'exec'))
