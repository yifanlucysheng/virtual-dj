import faulthandler
faulthandler.dump_traceback_later(60, exit=True)

import sounddevice as sd

def noStream(*args, **kwargs):
    raise RuntimeError('speakers turned off for this test')

sd.OutputStream = noStream
exec(compile(open('main.py').read(), 'main.py', 'exec'))
