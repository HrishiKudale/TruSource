# quick_serial_check.py  (pip install pyserial)
import serial, serial.tools.list_ports
print("Ports:", [p.device for p in serial.tools.list_ports.comports()])
PORT = "COM7"  # change if you picked another number
for baud in (57600, 115200):
    try:
        with serial.Serial(PORT, baudrate=baud, timeout=0.8) as s:
            print(f"Opened {PORT} at {baud}")
    except Exception as e:
        print(f"Failed {PORT} @ {baud}: {e}")
