import threading
import numpy as np

def start_audio_thread(socketio_instance):
    def audio_loop():
        PIPE_FFT = "/tmp/fft.pipe"
        FFT_SIZE = 1024
        chunk = FFT_SIZE * 4  # 2ch * 2bytes S16_LE

        while True:
            try:
                with open(PIPE_FFT, "rb", buffering=0) as f:
                    while True:
                        raw = f.read(chunk)
                        if len(raw) < chunk:
                            break
                        samples = np.frombuffer(raw, dtype=np.int16)
                        mono = (samples[0::2].astype(np.float32) + samples[1::2].astype(np.float32)) / 2
                        mono /= 32768.0
                        window = np.hanning(len(mono))
                        fft = np.abs(np.fft.rfft(mono * window))
                        fft = fft[:FFT_SIZE // 2]
                        fft = np.log1p(fft * 200)
                        mx = fft.max()
                        if mx > 0:
                            fft = fft / mx
                        bins = 64
                        step = len(fft) // bins
                        data = [float(round(fft[i*step:(i+1)*step].mean(), 3)) for i in range(bins)]
                        socketio_instance.emit('fft', data, namespace='/viz')
            except Exception:
                import time
                time.sleep(1)

    t = threading.Thread(target=audio_loop, daemon=True)
    t.start()
