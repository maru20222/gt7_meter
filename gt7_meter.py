import os
import socket
import struct
import time
import threading
import tkinter as tk
from Crypto.Cipher import Salsa20
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# --- 設定項目 ---
# IPアドレスは .env ファイルに記載してください（.env.example を参照）
PS_IP = os.getenv("PS_IP", "192.168.1.100")
# ----------------

# GT7のUDPポート仕様
UDP_PORT_SEND = 33739
UDP_PORT_RECV = 33740
HEARTBEAT_INTERVAL_SEC = 10
PACKET_MIN_SIZE = 368

# GT7専用の固定暗号キー（32バイト）
SALSA_KEY = b"Simulator Interface Packet GT7 ver 0.0"[:32]

# XOR定数（パケットバージョン別: A=0xDEADBEAF, B/C=0xDEADBEEF, ~=0x55FABB4F）
XOR_CONST = {
    'A': 0xDEADBEAF,
    'B': 0xDEADBEEF,
    'C': 0xDEADBEEF,
    '~': 0x55FABB4F,
}
PACKET_VERSION = 'C'

current_speed = 0
stop_event = threading.Event()

# 暗号解読関数（パケット全体を復号）
def decrypt_packet(payload):
    if len(payload) < 0x48:
        raise ValueError("パケットサイズが短すぎます")
    
    # 0x40〜0x44 からシードIVを取得（生バッファから読む）
    oiv = payload[0x40:0x44]
    iv1 = int.from_bytes(oiv, byteorder='little')
    
    # パケットバージョンに応じたXOR定数でnonce生成
    iv2 = iv1 ^ XOR_CONST[PACKET_VERSION]
    final_iv = struct.pack('<I', iv2) + struct.pack('<I', iv1)
    
    # パケット全体を復号（C++ライブラリと同じ方式）
    cipher = Salsa20.new(key=SALSA_KEY, nonce=final_iv)
    return cipher.decrypt(payload)

# UDP通信タスク（暗号化パケット対応）
def udp_worker():
    global current_speed
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', UDP_PORT_RECV))
    sock.settimeout(1.0)
    
    last_heartbeat = 0
    
    while not stop_event.is_set():
        now = time.time()
        # Packet C(368バイト)を引き出すため b'C' をハートビートとして送信
        if now - last_heartbeat > HEARTBEAT_INTERVAL_SEC:
            try:
                sock.sendto(PACKET_VERSION.encode(), (PS_IP, UDP_PORT_SEND))
                last_heartbeat = now
            except Exception as e:
                print("ハートビート送信エラー:", e)
        
        try:
            data, _ = sock.recvfrom(512)
            
            # 走行パケット（暗号化済み、368バイト）
            if len(data) >= PACKET_MIN_SIZE:
                decrypted = decrypt_packet(data)
                
                # 速度(float / m/s)はオフセット0x4C（構造体のspeedフィールド）
                speed_ms = struct.unpack('<f', decrypted[0x4C:0x50])[0]
                
                # 時速(km/h)に変換
                if 0 <= speed_ms < 1000:
                    current_speed = int(round(speed_ms * 3.6))
                else:
                    current_speed = 0
        except socket.timeout:
            current_speed = 0
        except Exception as e:
            print("データ処理エラー:", e)

    sock.close()

# 画面描画の処理 (Tkinter)
def update_gui():
    # 画面の数字を最新の速度に書き換える
    label_speed.config(text=f"{current_speed}")
    # 16ミリ秒後（約60Hz）に再度この関数を呼び出す
    root.after(16, update_gui)

# --- メイン画面構築 ---
root = tk.Tk()
root.title("GT7 Digital Speedometer")
root.geometry("800x480")
root.configure(bg='black')

# マウスのダブルクリックで「フルスクリーン」と「ウィンドウ表示」を切り替え
def toggle_fullscreen(event):
    is_full = root.attributes('-fullscreen')
    root.attributes('-fullscreen', not is_full)
root.bind('<Double-Button-1>', toggle_fullscreen)

def on_close():
    stop_event.set()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

# 速度の数字表示（フォントサイズや色は自由に変えられます）
label_speed = tk.Label(root, text="0", font=("Helvetica", 200, "bold"), fg="white", bg="black")
label_speed.pack(expand=True, pady=(50, 0))

# 単位表示
label_unit = tk.Label(root, text="km/h", font=("Helvetica", 30), fg="gray", bg="black")
label_unit.pack(expand=True, pady=(0, 50))

# UDP受信を別スレッドで開始
threading.Thread(target=udp_worker, daemon=True).start()

# 描画ループ開始
root.after(16, update_gui)
root.mainloop()
