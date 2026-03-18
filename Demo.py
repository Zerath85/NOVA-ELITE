import os
import threading
import time
import math
import webbrowser
import psutil
import subprocess
import requests
import json
from datetime import datetime
from groq import Groq
import customtkinter as ctk
import traceback
from dotenv import load_dotenv
from tkinter import filedialog
from PIL import Image
import PyPDF2
from bs4 import BeautifulSoup
from pyttsx3 import init as tts_init
from gtts import gTTS

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# =================================================================
# ⚙️ CORE CONFIGURATION
# =================================================================
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY", "API KEY BURAYA YAZILACAK")
MODEL = "llama-3.3-70b-versatile" 
WAKE_WORD = "nova"
NOTES_FILE = "nova_memory.json"
SETTINGS_FILE = "nova_settings.json"

class NovaElite(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NOVA ELITE - Yapay Zeka Asistanı")
        self.geometry("1000x950")
        self.configure(fg_color="#010101")
        
        self.is_speaking = False
        self.is_processing = False
        self.is_listening = False
        self.client = None
        self.animation_counter = 0
        self.mode = "text"
        self.current_material = None
        self.settings = self.load_settings()
        
        # TTS motorlarını başlat
        self.tts_engine = self.init_tts()
        
        self.init_groq_client()
        self.setup_ui()
        self.load_memory()
        
        threading.Thread(target=self.hologram_engine, daemon=True).start()

    def init_tts(self):
        """TTS motorunu başlat - pyttsx3"""
        try:
            engine = tts_init()
            voices = engine.getProperty('voices')
            
            # Kadın sesi bul
            for voice in voices:
                if 'female' in voice.name.lower() or 'woman' in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    break
            
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 0.9)
            
            return engine
        except Exception as e:
            print(f"TTS başlatma hatası: {e}")
            return None

    def init_groq_client(self):
        try:
            self.client = Groq(api_key=API_KEY)
            test = self.client.chat.completions.create(
                messages=[{"role": "user", "content": "test"}],
                model=MODEL,
                max_tokens=5
            )
            print("✓ Groq API Başarılı!")
            return True
        except Exception as e:
            print(f"✗ API Hatası: {e}")
            self.client = None
            return False

    def log_terminal(self, msg):
        """Log mesajı yaz"""
        try:
            ts = datetime.now().strftime("%H:%M:%S")
            self.terminal.insert("end", f"[{ts}] {msg}\n")
            self.terminal.see("end")
        except:
            print(msg)

    def setup_ui(self):
        """Arayüzü kur"""
        
        # Sol panel
        left_panel = ctk.CTkFrame(self, fg_color="#0a0a0a", width=200)
        left_panel.pack(side="left", fill="y", padx=10, pady=10)
        left_panel.pack_propagate(False)
        
        settings_btn = ctk.CTkButton(
            left_panel,
            text="⚙️ Ayarlar",
            command=self.open_settings,
            width=180,
            height=40,
            font=("Arial", 12, "bold")
        )
        settings_btn.pack(pady=20)
        
        # Ana panel
        main_panel = ctk.CTkFrame(self, fg_color="#010101")
        main_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        # Header
        header = ctk.CTkFrame(main_panel, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=10)
        
        self.status_ind = ctk.CTkLabel(
            header, 
            text="⚡ READY", 
            font=("Arial", 14, "bold"), 
            text_color="#00fbff"
        )
        self.status_ind.pack(side="left")
        
        self.info_label = ctk.CTkLabel(
            header,
            text="Yazı modu aktif - komut yazın",
            font=("Arial", 11),
            text_color="#00ff88"
        )
        self.info_label.pack(side="left", padx=20)

        # Canvas
        self.canvas = ctk.CTkCanvas(
            main_panel, 
            width=900, 
            height=280, 
            bg="#010101", 
            highlightthickness=0
        )
        self.canvas.pack(pady=10)

        # Halkalar
        self.rings = []
        center_x, center_y = 450, 140
        
        for i in range(8):
            r = self.canvas.create_oval(0, 0, 100, 100, outline="#002222", width=2)
            self.rings.append(r)
        
        # Merkez Orb
        self.core_orb = self.canvas.create_oval(400, 90, 500, 190, outline="#00fbff", fill="#001a1a", width=4)

        # Status Frame
        status_f = ctk.CTkFrame(main_panel, fg_color="#080808")
        status_f.pack(fill="x", padx=20, pady=5)
        
        self.fps_label = ctk.CTkLabel(
            status_f,
            text="FPS: 30 | API: CONNECTED | STATUS: READY",
            font=("Courier", 9),
            text_color="#00ff88"
        )
        self.fps_label.pack(padx=10, pady=5)

        # Terminal
        self.terminal = ctk.CTkTextbox(
            main_panel, 
            width=900, 
            height=350, 
            fg_color="#0a0a0a", 
            text_color="#00ffcc", 
            font=("Courier", 14)
        )
        self.terminal.pack(pady=10, padx=20)
        
        self.log_terminal("[NOVA] Sistem başlatıldı...")
        self.log_terminal("[✓] Groq API Bağlandı" if self.client else "[✗] API HATASI")
        self.log_terminal("[✓] Yazı modu aktif")
        self.log_terminal("[🔊] gTTS + pyttsx3 Hibrit Ses Sistemi Aktif\n")

        # Yükleme butonları
        upload_frame = ctk.CTkFrame(main_panel, fg_color="transparent")
        upload_frame.pack(fill="x", padx=20, pady=5)
        
        self.pdf_btn = ctk.CTkButton(
            upload_frame,
            text="📄 PDF Yükle",
            command=self.load_pdf,
            width=150,
            height=30
        )
        self.pdf_btn.pack(side="left", padx=5)
        
        self.image_btn = ctk.CTkButton(
            upload_frame,
            text="🖼️ Görsel Yükle",
            command=self.load_image,
            width=150,
            height=30
        )
        self.image_btn.pack(side="left", padx=5)
        
        self.link_btn = ctk.CTkButton(
            upload_frame,
            text="🔗 Link Analiz Et",
            command=self.analyze_link,
            width=150,
            height=30
        )
        self.link_btn.pack(side="left", padx=5)

        # Input Frame
        self.input_frame = ctk.CTkFrame(main_panel, fg_color="transparent")
        self.input_frame.pack(fill="x", padx=20, pady=10)
        
        self.input_entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Komut yaz... (örn: nova merhaba)",
            width=700,
            height=35
        )
        self.input_entry.pack(side="left", padx=5)
        self.input_entry.bind("<Return>", lambda e: self.on_send())
        
        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="Gönder",
            command=self.on_send,
            width=100,
            height=35
        )
        self.send_btn.pack(side="left", padx=5)

    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {
                "hitap": "Sen",
                "ses_aktif": True,
                "tema": "dark",
                "dil": "tr",
                "ses_hizi": 150,
                "ses_seviyesi": 0.9,
                "ses_sistemi": "gtts"  # gtts veya pyttsx3
            }
        except:
            return {
                "hitap": "Sen",
                "ses_aktif": True,
                "tema": "dark",
                "dil": "tr",
                "ses_hizi": 150,
                "ses_seviyesi": 0.9,
                "ses_sistemi": "gtts"
            }

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log_terminal(f"[✗] Ayarlar kaydedilemedi: {e}")

    def open_settings(self):
        settings_window = ctk.CTkToplevel(self)
        settings_window.title("NOVA Ayarları")
        settings_window.geometry("500x750")
        settings_window.configure(fg_color="#010101")
        
        title = ctk.CTkLabel(
            settings_window,
            text="⚙️ Kişiselleştirme Ayarları",
            font=("Arial", 18, "bold"),
            text_color="#00fbff"
        )
        title.pack(pady=20)
        
        # Hitap
        hitap_frame = ctk.CTkFrame(settings_window, fg_color="#0a0a0a")
        hitap_frame.pack(fill="x", padx=20, pady=10)
        
        hitap_label = ctk.CTkLabel(hitap_frame, text="🤖 Bana nasıl hitap etsin?", font=("Arial", 12))
        hitap_label.pack(pady=10)
        
        hitap_combo = ctk.CTkComboBox(
            hitap_frame,
            values=["Sen", "Siz", "Efendim", "Patron", "Arkadaş"],
            state="normal"
        )
        hitap_combo.set(self.settings.get("hitap", "Sen"))
        hitap_combo.pack(pady=10)
        
        # Ses
        ses_frame = ctk.CTkFrame(settings_window, fg_color="#0a0a0a")
        ses_frame.pack(fill="x", padx=20, pady=10)
        
        ses_label = ctk.CTkLabel(ses_frame, text="🔊 Ses Ayarları", font=("Arial", 12))
        ses_label.pack(pady=10)
        
        ses_switch = ctk.CTkSwitch(
            ses_frame,
            text="Sesli cevap aktif",
            onvalue=True,
            offvalue=False
        )
        ses_switch.select() if self.settings.get("ses_aktif", True) else ses_switch.deselect()
        ses_switch.pack(pady=5)
        
        # Ses Sistemi
        sistem_label = ctk.CTkLabel(ses_frame, text="Ses Sistemi", font=("Arial", 10))
        sistem_label.pack(pady=5)
        
        sistem_combo = ctk.CTkComboBox(
            ses_frame,
            values=["gTTS (İnternet - Daha Güzel)", "pyttsx3 (Offline - Hızlı)"],
            state="normal"
        )
        current_sistem = self.settings.get("ses_sistemi", "gtts")
        sistem_combo.set("gTTS (İnternet - Daha Güzel)" if current_sistem == "gtts" else "pyttsx3 (Offline - Hızlı)")
        sistem_combo.pack(pady=10)
        
        # Ses hızı
        hiz_label = ctk.CTkLabel(ses_frame, text="Konuşma Hızı", font=("Arial", 10))
        hiz_label.pack(pady=5)
        
        hiz_slider = ctk.CTkSlider(
            ses_frame,
            from_=50,
            to=300,
            number_of_steps=25
        )
        hiz_slider.set(self.settings.get("ses_hizi", 150))
        hiz_slider.pack(pady=5)
        
        hiz_value = ctk.CTkLabel(ses_frame, text="150 (Normal)", font=("Arial", 9))
        hiz_value.pack()
        
        def update_hiz(val):
            hiz_value.configure(text=f"{int(float(val))} ({'Çok Yavaş' if float(val) < 100 else 'Yavaş' if float(val) < 150 else 'Normal' if float(val) < 200 else 'Hızlı' if float(val) < 250 else 'Çok Hızlı'})")
        
        hiz_slider.configure(command=update_hiz)
        
        # Ses seviyesi
        volume_label = ctk.CTkLabel(ses_frame, text="Ses Seviyesi", font=("Arial", 10))
        volume_label.pack(pady=5)
        
        volume_slider = ctk.CTkSlider(
            ses_frame,
            from_=0.1,
            to=1.0,
            number_of_steps=9
        )
        volume_slider.set(self.settings.get("ses_seviyesi", 0.9))
        volume_slider.pack(pady=5)
        
        volume_value = ctk.CTkLabel(ses_frame, text="90%", font=("Arial", 9))
        volume_value.pack()
        
        def update_volume(val):
            volume_value.configure(text=f"{int(float(val) * 100)}%")
        
        volume_slider.configure(command=update_volume)
        
        # Test butonu
        test_btn = ctk.CTkButton(
            ses_frame,
            text="🎤 Ses Testi Yap",
            command=lambda: self.test_voice(hiz_slider.get(), volume_slider.get()),
            width=150,
            height=30
        )
        test_btn.pack(pady=10)
        
        # Tema
        tema_frame = ctk.CTkFrame(settings_window, fg_color="#0a0a0a")
        tema_frame.pack(fill="x", padx=20, pady=10)
        
        tema_label = ctk.CTkLabel(tema_frame, text="🎨 Tema seçimi", font=("Arial", 12))
        tema_label.pack(pady=10)
        
        tema_combo = ctk.CTkComboBox(
            tema_frame,
            values=["Dark", "Light", "Blue"],
            state="normal"
        )
        tema_combo.set(self.settings.get("tema", "dark").capitalize())
        tema_combo.pack(pady=10)
        
        # Dil
        dil_frame = ctk.CTkFrame(settings_window, fg_color="#0a0a0a")
        dil_frame.pack(fill="x", padx=20, pady=10)
        
        dil_label = ctk.CTkLabel(dil_frame, text="🌍 Dil seçimi", font=("Arial", 12))
        dil_label.pack(pady=10)
        
        dil_combo = ctk.CTkComboBox(
            dil_frame,
            values=["Türkçe", "English"],
            state="normal"
        )
        dil_combo.set("Türkçe" if self.settings.get("dil", "tr") == "tr" else "English")
        dil_combo.pack(pady=10)
        
        def save_and_close():
            self.settings["hitap"] = hitap_combo.get()
            self.settings["ses_aktif"] = ses_switch.get()
            self.settings["ses_hizi"] = int(float(hiz_slider.get()))
            self.settings["ses_seviyesi"] = float(volume_slider.get())
            self.settings["tema"] = tema_combo.get().lower()
            self.settings["dil"] = "tr" if dil_combo.get() == "Türkçe" else "en"
            self.settings["ses_sistemi"] = "gtts" if "gTTS" in sistem_combo.get() else "pyttsx3"
            
            self.save_settings()
            
            # TTS ayarlarını güncelle
            if self.tts_engine:
                self.tts_engine.setProperty('rate', self.settings["ses_hizi"])
                self.tts_engine.setProperty('volume', self.settings["ses_seviyesi"])
            
            self.log_terminal("[✓] Ses ayarları kaydedildi")
            settings_window.destroy()
        
        save_btn = ctk.CTkButton(
            settings_window,
            text="💾 Kaydet ve Kapat",
            command=save_and_close,
            width=200,
            height=40
        )
        save_btn.pack(pady=20)

    def test_voice(self, hiz, volume):
        """Ses testiyle yap"""
        self.speak("Merhaba! Ben NOVA yapay zeka asistanınım. Bu benim sesim, nasıl geliyor?")

    def load_pdf(self):
        file_path = filedialog.askopenfilename(
            title="PDF Dosyası Seç",
            filetypes=[("PDF files", "*.pdf")]
        )
        if file_path:
            self.log_terminal(f"[📄] PDF yükleniyor: {os.path.basename(file_path)}")
            try:
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text()
                    
                    self.current_material = {"type": "pdf", "content": text, "path": file_path}
                    self.log_terminal(f"[✓] PDF yüklendi: {len(text)} karakter")
                    self.log_terminal("Şimdi 'pdf analiz et' yazarak analiz ettirebilirsin")
                    
            except Exception as e:
                self.log_terminal(f"[✗] PDF yükleme hatası: {e}")

    def load_image(self):
        file_path = filedialog.askopenfilename(
            title="Görsel Dosyası Seç",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        if file_path:
            self.log_terminal(f"[🖼️] Görsel yükleniyor: {os.path.basename(file_path)}")
            try:
                img = Image.open(file_path)
                self.current_material = {"type": "image", "image": img, "path": file_path}
                self.log_terminal(f"[✓] Görsel yüklendi: {img.size}")
                self.log_terminal("Şimdi 'görsel analiz et' yazarak analiz ettirebilirsin")
                
            except Exception as e:
                self.log_terminal(f"[✗] Görsel yükleme hatası: {e}")

    def analyze_link(self):
        dialog = ctk.CTkInputDialog(text="Link girin:", title="Link Analizi")
        link = dialog.get_input()
        
        if link:
            self.log_terminal(f"[🔗] Link analiz ediliyor: {link}")
            try:
                response = requests.get(link, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                title = soup.title.string if soup.title else "Başlık bulunamadı"
                text = soup.get_text()
                
                self.current_material = {"type": "link", "title": title, "content": text, "url": link}
                self.log_terminal(f"[✓] Link analiz edildi: {title}")
                self.log_terminal("Şimdi 'link analiz et' yazarak detaylı analiz ettirebilirsin")
                
            except Exception as e:
                self.log_terminal(f"[✗] Link analiz hatası: {e}")

    def on_send(self):
        cmd = self.input_entry.get().strip()
        self.input_entry.delete(0, "end")
        if cmd:
            res = self.process_command(cmd)

    def update_status(self, text, color):
        try:
            self.status_ind.configure(text=text, text_color=color)
        except:
            pass

    def hologram_engine(self):
        t = 0
        frame = 0
        start = time.time()
        
        ring_variations = []
        for i in range(len(self.rings)):
            variation = {
                "speed": 0.02 + (i * 0.01),
                "color_shift": i * 0.5,
                "pulse_freq": 2 + (i * 0.3),
                "random_offset": i * 0.1
            }
            ring_variations.append(variation)
        
        while True:
            try:
                t += 0.04
                frame += 1
                
                if frame % 30 == 0:
                    elapsed = time.time() - start
                    fps = 30 / elapsed if elapsed > 0 else 0
                    start = time.time()
                    self.fps_label.configure(
                        text=f"FPS: {int(fps)} | API: {'✓' if self.client else '✗'} | STATUS: {'SPEAKING' if self.is_speaking else 'PROCESSING' if self.is_processing else 'READY'}"
                    )
                
                base_color = "#ff1744" if self.is_speaking else "#ffaa00" if self.is_processing else "#00ff88" if self.is_listening else "#00fbff"
                
                center_x, center_y = 450, 140
                
                for i, (ring, var) in enumerate(zip(self.rings, ring_variations)):
                    local_t = t * var["speed"] + var["random_offset"]
                    
                    base_size = 40 + (i * 20)
                    pulse = math.sin(local_t * var["pulse_freq"]) * 15
                    size = base_size + pulse
                    
                    random_x = math.sin(local_t * 1.5) * 10
                    random_y = math.cos(local_t * 1.2) * 8
                    
                    x1 = center_x - size + random_x
                    y1 = center_y - (size * 0.6) + random_y
                    x2 = center_x + size + random_x
                    y2 = center_y + (size * 0.6) + random_y
                    
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(900, x2)
                    y2 = min(280, y2)
                    
                    self.canvas.coords(ring, x1, y1, x2, y2)
                    
                    hue_shift = var["color_shift"] + local_t
                    if base_color == "#ff1744":
                        ring_color = "#ff1744" if i % 3 == 0 else "#ff5722" if i % 3 == 1 else "#d84315"
                    elif base_color == "#ffaa00":
                        ring_color = "#ffaa00" if i % 3 == 0 else "#ff8f00" if i % 3 == 1 else "#ef6c00"
                    elif base_color == "#00ff88":
                        ring_color = "#00ff88" if i % 3 == 0 else "#00e676" if i % 3 == 1 else "#00c853"
                    else:
                        ring_color = "#00fbff" if i % 3 == 0 else "#00e5ff" if i % 3 == 1 else "#00b8d4"
                    
                    self.canvas.itemconfig(ring, outline=ring_color)
                
                if self.is_speaking:
                    pulse = 40 + (math.sin(t * 12) * 18) + (math.cos(t * 8) * 8)
                elif self.is_processing:
                    pulse = 40 + (math.sin(t * 6) * 12) + (math.sin(t * 10) * 5)
                else:
                    pulse = 40 + (math.sin(t * 2) * 6) + (math.cos(t * 3) * 4)
                
                pulse = max(20, pulse)
                
                x1 = center_x - pulse
                y1 = center_y - (pulse * 0.6)
                x2 = center_x + pulse
                y2 = center_y + (pulse * 0.6)
                
                self.canvas.coords(self.core_orb, x1, y1, x2, y2)
                self.canvas.itemconfig(self.core_orb, outline=base_color)
                
                time.sleep(0.03)
                
            except Exception as e:
                print(f"Animate Error: {e}")
                time.sleep(0.1)

    def load_memory(self):
        try:
            if not os.path.exists(NOTES_FILE):
                with open(NOTES_FILE, "w", encoding="utf-8") as f:
                    json.dump({"history": []}, f)
            self.log_terminal("[✓] Bellek yüklendi")
        except Exception as e:
            self.log_terminal(f"[✗] Bellek hatası: {e}")

    def save_memory(self, user, response):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["history"].append({
                "time": datetime.now().isoformat(),
                "user": user,
                "nova": response
            })
            with open(NOTES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except:
            pass

    def speak(self, text):
        """Sesli cevap - Hibrit gTTS + pyttsx3"""
        def _task():
            self.is_speaking = True
            try:
                self.log_terminal(f"[🔊 SPEAKING] {text[:50]}...")
                
                ses_sistemi = self.settings.get("ses_sistemi", "gtts")
                
                if ses_sistemi == "gtts":
                    # gTTS kullan
                    self._speak_gtts(text)
                else:
                    # pyttsx3 kullan
                    self._speak_pyttsx3(text)
                
                self.log_terminal("[✓] Ses tamamlandı")
                
            except Exception as e:
                self.log_terminal(f"[✗] Ses hatası: {e}")
            finally:
                self.is_speaking = False
        
        threading.Thread(target=_task, daemon=True).start()

    def _speak_gtts(self, text):
        """gTTS ile konuş"""
        try:
            fname = os.path.join(os.getcwd(), f"nova_{int(time.time())}.mp3")
            
            # MP3 oluştur
            tts = gTTS(text=text, lang='tr', slow=False)
            tts.save(fname)
            
            # Dosya oluşturulduğunu kontrol et
            if not os.path.exists(fname):
                self.log_terminal("[!] gTTS başarısız, pyttsx3'e düşülüyor...")
                self._speak_pyttsx3(text)
                return
            
            if PYGAME_AVAILABLE:
                # Pygame ile oynat
                pygame.mixer.init()
                pygame.mixer.music.set_volume(self.settings.get("ses_seviyesi", 0.9))
                pygame.mixer.music.load(fname)
                pygame.mixer.music.play()
                
                # Oynatmayı bekle
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                
                pygame.mixer.quit()
                time.sleep(0.5)
            else:
                self.log_terminal("[!] Pygame yok, pyttsx3'e düşülüyor...")
                self._speak_pyttsx3(text)
            
            # Dosyayı sil
            try:
                if os.path.exists(fname):
                    os.remove(fname)
            except:
                pass
                
        except Exception as e:
            self.log_terminal(f"[!] gTTS hatası: {e}, pyttsx3'e düşülüyor...")
            self._speak_pyttsx3(text)

    def _speak_pyttsx3(self, text):
        """pyttsx3 ile konuş - Offline fallback"""
        try:
            if self.tts_engine:
                self.tts_engine.setProperty('rate', self.settings.get("ses_hizi", 150))
                self.tts_engine.setProperty('volume', self.settings.get("ses_seviyesi", 0.9))
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            else:
                self.log_terminal("[!] TTS motoru kullanılamıyor")
        except Exception as e:
            self.log_terminal(f"[!] pyttsx3 hatası: {e}")

    def process_command(self, cmd):
        cmd = cmd.lower().strip()
        self.log_terminal(f"[👤] {cmd}")
        self.is_processing = True
        
        if not cmd:
            self.is_processing = False
            return "Anlamadım"

        if "pdf analiz et" in cmd:
            if self.current_material and self.current_material["type"] == "pdf":
                analysis = self.analyze_material("PDF'yi analiz et ve özetle: " + self.current_material["content"][:2000])
                self.is_processing = False
                self.speak(analysis)
                return analysis
            else:
                self.is_processing = False
                msg = "Önce PDF yükleyin"
                self.speak(msg)
                return msg
        
        if "görsel analiz et" in cmd:
            if self.current_material and self.current_material["type"] == "image":
                analysis = self.analyze_material("Bu görselde ne görüyorsun? Detaylı tarif et.")
                self.is_processing = False
                self.speak(analysis)
                return analysis
            else:
                self.is_processing = False
                msg = "Önce görsel yükleyin"
                self.speak(msg)
                return msg
        
        if "link analiz et" in cmd:
            if self.current_material and self.current_material["type"] == "link":
                analysis = self.analyze_material(f"Bu web sayfasını analiz et: {self.current_material['title']} - {self.current_material['content'][:2000]}")
                self.is_processing = False
                self.speak(analysis)
                return analysis
            else:
                self.is_processing = False
                msg = "Önce link analiz edin"
                self.speak(msg)
                return msg

        if "saat" in cmd:
            result = datetime.now().strftime("Saat %H:%M:%S")
            self.is_processing = False
            self.speak(result)
            return result
        
        if "sistem" in cmd:
            cpu = psutil.cpu_percent(0.5)
            ram = psutil.virtual_memory().percent
            result = f"CPU {cpu}% RAM {ram}%"
            self.is_processing = False
            self.speak(result)
            return result
        
        if "temizle" in cmd:
            self.terminal.delete("1.0", "end")
            self.is_processing = False
            self.log_terminal("[NOVA] Terminal temizlendi")
            return "Terminal temizlendi"

        if not self.client:
            self.is_processing = False
            msg = "API bağlantısı yok"
            self.speak(msg)
            return msg

        try:
            hitap = self.settings.get("hitap", "Sen")
            system_msg = f"Sen NOVA yapay zeka asistanısın. Kullanıcıya '{hitap}' diye hitap et. Türkçe cevap ver. Kısa ve öz."
            
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": cmd}
                ],
                model=MODEL,
                max_tokens=150,
                temperature=0.7
            )
            result = response.choices[0].message.content
            self.is_processing = False
            self.log_terminal(f"[🤖] {result}")
            self.save_memory(cmd, result)
            
            if self.settings.get("ses_aktif", True):
                self.speak(result)
            
            return result
        except Exception as e:
            self.is_processing = False
            self.log_terminal(f"[✗] API: {str(e)[:50]}")
            error_msg = "API hatası"
            self.speak(error_msg)
            return error_msg

    def analyze_material(self, prompt):
        if not self.client:
            return "API bağlantısı yok"
        
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Sen bir analiz asistanısın. Türkçe cevap ver. Detaylı ve yardımcı ol."},
                    {"role": "user", "content": prompt}
                ],
                model=MODEL,
                max_tokens=300,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Analiz hatası: {e}"

if __name__ == "__main__":
    app = NovaElite()
    app.mainloop()