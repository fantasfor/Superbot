import pyautogui
import cv2
import numpy as np
import time
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import keyboard
import pytesseract
from datetime import datetime
from PIL import Image, ImageTk
import shutil
import sys
import urllib.request
import subprocess

try:
    from pynput import mouse as pynput_mouse
    from pynput import keyboard as pynput_keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    pynput_mouse = None
    pynput_keyboard = None

# Desabilitar fail-safe do PyAutoGUI
pyautogui.FAILSAFE = False

# Configuração do Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Versão do programa
VERSION = "1.0.1"
UPDATE_URL = "https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/version.json"  # Altere para seu repositório
DOWNLOAD_URL = "https://github.com/SEU_USUARIO/SEU_REPO/releases/latest/download/GDMmacrobot.exe"  # Altere para seu repositório

def check_for_updates():
    """Verifica se há atualizações disponíveis"""
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=5) as response:
            data = json.loads(response.read().decode())
            latest_version = data.get("version", VERSION)
            changelog = data.get("changelog", "Sem informações")
            
            if latest_version > VERSION:
                return True, latest_version, changelog
            return False, VERSION, ""
    except Exception as e:
        print(f"Erro ao verificar atualizações: {e}")
        return False, VERSION, ""

def download_update(progress_callback=None):
    """Baixa a atualização"""
    try:
        temp_file = "GDMmacrobot_new.exe"
        
        def report_progress(block_num, block_size, total_size):
            if progress_callback and total_size > 0:
                downloaded = block_num * block_size
                percent = min(int((downloaded / total_size) * 100), 100)
                progress_callback(percent)
        
        urllib.request.urlretrieve(DOWNLOAD_URL, temp_file, reporthook=report_progress)
        return True, temp_file
    except Exception as e:
        return False, str(e)

def apply_update(new_exe_path):
    """Aplica a atualização substituindo o executável"""
    try:
        current_exe = sys.executable
        backup_exe = current_exe + ".backup"
        
        # Criar backup do executável atual
        if os.path.exists(current_exe):
            shutil.copy2(current_exe, backup_exe)
        
        # Criar script batch para substituir o executável
        batch_script = """@echo off
timeout /t 2 /nobreak > nul
del "{old_exe}"
move /y "{new_exe}" "{old_exe}"
start "" "{old_exe}"
del "%~f0"
""".format(old_exe=current_exe, new_exe=new_exe_path)
        
        batch_file = "update_script.bat"
        with open(batch_file, "w") as f:
            f.write(batch_script)
        
        # Executar o script e fechar o programa
        subprocess.Popen([batch_file], shell=True)
        return True
    except Exception as e:
        return False

def get_resource_path(relative_path):
    """Obtém o caminho correto para recursos, funcionando tanto em desenvolvimento quanto em executável PyInstaller"""
    try:
        # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Se não estiver rodando como executável, usa o caminho normal
        base_path = os.path.dirname(__file__)
    
    return os.path.join(base_path, relative_path)

# ==================== CONFIGURAÇÕES ====================
class Config:
    def __init__(self):
        self.data = {
            "folder": "targets",
            "threshold": 0.80,
            "delay_global": 0.1,
            "delay_between_actions": 0.5,
            "initial_delay": 3.0,
            "loop_mode": "infinite",
            "loop_count": 1,
            "hotkey_start": "f9",
            "hotkey_stop": "f10",
            "hotkey_record": "f5",
            "ocr_lang": "por+eng",
            "ocr_preprocess": "adaptive",
            "click_duration": 0.1,
            "safety_delay": 0.05,
            "max_retries": 3
        }
        self.load()
    
    def load(self):
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    self.data.update(json.load(f))
            except:
                pass
    
    def save(self):
        with open("config.json", "w") as f:
            json.dump(self.data, f, indent=4)

# ==================== CORE DO BOT ====================
class MacroBot:
    def __init__(self):
        self.running = False
        self.config = Config()
        self.commands = []
        self.targets_cache = {}
        self.stats = {
            "executions": 0,
            "clicks": 0,
            "keys_pressed": 0,
            "errors": 0,
            "start_time": None
        }
        self.log_callback = None
        
    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {msg}"
        if self.log_callback:
            self.log_callback(formatted, level)
        print(formatted)
    
    def load_targets(self):
        """Carrega imagens alvo com cache otimizado"""
        folder = self.config.data["folder"]
        if not os.path.exists(folder):
            os.makedirs(folder)
            return {}
        
        images = {}
        valid_extensions = (".png", ".jpg", ".jpeg", ".bmp")
        
        try:
            files = [f for f in os.listdir(folder) if f.lower().endswith(valid_extensions)]
            for file in files:
                path = os.path.join(folder, file)
                try:
                    img = cv2.imread(path, cv2.IMREAD_COLOR)
                    if img is not None:
                        images[file] = img
                except Exception as e:
                    self.log(f"Erro ao carregar {file}: {e}", "ERROR")
        except Exception as e:
            self.log(f"Erro ao acessar pasta {folder}: {e}", "ERROR")
        
        self.targets_cache = images
        return images
    
    def find_image(self, target_img, threshold=None, region=None):
        """Encontra imagem na tela com opções avançadas - otimizado"""
        threshold = threshold or self.config.data["threshold"]
        
        screenshot = pyautogui.screenshot(region=region)
        screenshot_array = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot_array, cv2.COLOR_RGB2GRAY)
        target_gray = cv2.cvtColor(target_img, cv2.COLOR_BGR2GRAY)
        
        result = cv2.matchTemplate(screenshot_gray, target_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= threshold:
            h, w = target_gray.shape
            x = max_loc[0] + (w >> 1)  # Bit shift é mais rápido que divisão
            y = max_loc[1] + (h >> 1)
            
            if region:
                x += region[0]
                y += region[1]
            
            return (x, y), max_val
        
        return None, max_val
    
    def find_all_images(self, target_img, threshold=None):
        """Encontra todas ocorrências de uma imagem - otimizado"""
        threshold = threshold or self.config.data["threshold"]
        
        screenshot = pyautogui.screenshot()
        screenshot_array = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot_array, cv2.COLOR_RGB2GRAY)
        target_gray = cv2.cvtColor(target_img, cv2.COLOR_BGR2GRAY)
        
        result = cv2.matchTemplate(screenshot_gray, target_gray, cv2.TM_CCOEFF_NORMED)
        h, w = target_gray.shape
        
        loc = np.where(result >= threshold)
        half_w, half_h = w >> 1, h >> 1
        return [(pt[0] + half_w, pt[1] + half_h) for pt in zip(*loc[::-1])]
    
    def preprocess_image_for_ocr(self, image, method="adaptive"):
        """Pré-processa imagem para melhorar OCR"""
        # Converte para escala de cinza se necessário
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        if method == "threshold":
            # Binarização simples
            _, processed = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        elif method == "adaptive":
            # Binarização adaptativa (melhor para textos com sombras/fundos variados)
            processed = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
        
        elif method == "otsu":
            # Método de Otsu (automático)
            _, processed = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        elif method == "contrast":
            # Aumenta contraste
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            processed = clahe.apply(gray)
        
        elif method == "denoise":
            # Remove ruído e aumenta contraste
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            processed = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
        
        elif method == "invert":
            # Inverte cores (útil para texto branco em fundo escuro)
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            processed = cv2.bitwise_not(binary)
        
        else:  # none
            processed = gray
        
        # Aplica dilatação/erosão para melhorar legibilidade
        kernel = np.ones((2,2), np.uint8)
        processed = cv2.dilate(processed, kernel, iterations=1)
        processed = cv2.erode(processed, kernel, iterations=1)
        
        return processed
    
    def find_text_ocr(self, text, case_sensitive=False, region=None, color_filter=None):
        """Busca texto usando OCR com melhorias de pré-processamento
        
        Args:
            text: Texto para buscar
            case_sensitive: Se deve diferenciar maiúsculas/minúsculas
            region: Tupla (x, y, width, height) para limitar área de busca
            color_filter: Tupla com range de cores HSV para filtrar texto colorido
                         Exemplo: ((0, 100, 100), (10, 255, 255)) para vermelho
        """
        try:
            # Captura screenshot
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            
            img = np.array(screenshot)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            # Se especificou filtro de cor, tenta isolar a cor primeiro
            if color_filter:
                hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                lower_color, upper_color = color_filter
                mask = cv2.inRange(hsv, np.array(lower_color), np.array(upper_color))
                
                # Aplica máscara para isolar texto colorido
                img_filtered = cv2.bitwise_and(img_bgr, img_bgr, mask=mask)
                gray = cv2.cvtColor(img_filtered, cv2.COLOR_BGR2GRAY)
            else:
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            
            # Usa apenas o método configurado
            method = self.config.data.get("ocr_preprocess", "adaptive")
            processed = self.preprocess_image_for_ocr(gray, method)
            
            ocr_lang = self.config.data.get("ocr_lang", "por+eng")
            custom_config = r'--oem 3 --psm 6'  # PSM 6 = assume bloco único de texto
            
            ocr_result = pytesseract.image_to_string(
                processed,
                lang=ocr_lang,
                config=custom_config
            )
            
            # Verifica se encontrou o texto
            if case_sensitive:
                found = text in ocr_result
            else:
                found = text.lower() in ocr_result.lower()
            
            if found:
                self.log(f"✓ OCR encontrou texto '{text}'")
            else:
                self.log(f"✗ OCR não encontrou texto: '{text}'", "WARN")
            
            return found
            
        except Exception as e:
            self.log(f"Erro OCR: {e}", "ERROR")
            return False
    
    def dfind_text_ocr_advanced(self, text, case_sensitive=False):
        """Busca texto com detecção automática de múltiplas cores"""
        # Define ranges de cores comuns em textos de jogos
        color_ranges = [
            # Branco/Claro
            ((0, 0, 200), (180, 30, 255)),
            # Vermelho 1
            ((0, 100, 100), (10, 255, 255)),
            # Vermelho 2
            ((160, 100, 100), (180, 255, 255)),
            # Amarelo
            ((20, 100, 100), (30, 255, 255)),
            # Laranja
            ((10, 100, 100), (20, 255, 255)),
            # Verde
            ((40, 100, 100), (80, 255, 255)),
            # Ciano/Azul claro
            ((85, 100, 100), (95, 255, 255)),
            # Azul
            ((100, 100, 100), (130, 255, 255)),
        ]
        
        # Tenta com cada filtro de cor
        for color_range in color_ranges:
            if self.find_text_ocr(text, case_sensitive, color_filter=color_range):
                return True
        
        # Tenta sem filtro de cor (texto escuro em fundo claro)
        return self.find_text_ocr(text, case_sensitive)
    
    def execute_command(self, cmd):
        """Executa um comando individual"""
        tipo = cmd.get("type")
        value = cmd.get("value", "")
        options = cmd.get("options", {})
        
        try:
            # CLICK IMAGE
            if tipo == "click_image":
                if value in self.targets_cache:
                    pos, confidence = self.find_image(self.targets_cache[value])
                    if pos:
                        # Verifica se deve usar clique variável
                        click_mode = options.get("click_mode", "fixed")
                        click_action = options.get("click_action", "normal")  # normal, down, up
                        x, y = pos

                        if click_mode == "variable":
                            radius = options.get("click_radius", 5)
                            offset_x = np.random.randint(-radius, radius + 1)
                            offset_y = np.random.randint(-radius, radius + 1)
                            x += offset_x
                            y += offset_y
                            self.log(f"✓ Clique variável: offset ({offset_x}, {offset_y})")

                        button = options.get("button", "left")

                        if click_action == "down":
                            pyautogui.mouseDown(x, y, button=button)
                            self.log(f"🖱 Mouse down em {value} ({x},{y}) - Botão: {button}")
                        elif click_action == "up":
                            pyautogui.mouseUp(x, y, button=button)
                            self.log(f"🖱 Mouse up em {value} ({x},{y}) - Botão: {button}")
                        else:  # normal
                            clicks = options.get("clicks", 1)
                            hold_time = options.get("hold_time", 0)

                            # Se tiver tempo de segurar
                            if hold_time > 0:
                                pyautogui.mouseDown(x, y, button=button)
                                time.sleep(hold_time)
                                pyautogui.mouseUp(x, y, button=button)
                                self.log(f"✓ Segurou botão por {hold_time}s")
                            else:
                                pyautogui.click(
                                    x, y,
                                    clicks=clicks,
                                    button=button,
                                    duration=self.config.data["click_duration"]
                                )

                            self.stats["clicks"] += clicks
                            self.log(f"✓ Clicou em {value} ({x},{y}) - Confiança: {confidence:.2%}")

                        return True
                    else:
                        self.log(f"✗ Imagem não encontrada: {value}", "WARN")
                        return False
            
            # CLICK (apenas clicar, sem buscar imagem)
            elif tipo == "click":
                click_mode = options.get("click_mode", "fixed")
                click_action = options.get("click_action", "normal")  # normal, down, up
                x, y = pyautogui.position()

                if click_mode == "variable":
                    radius = options.get("click_radius", 5)
                    offset_x = np.random.randint(-radius, radius + 1)
                    offset_y = np.random.randint(-radius, radius + 1)
                    x += offset_x
                    y += offset_y

                button = options.get("button", "left")

                if click_action == "down":
                    pyautogui.mouseDown(x, y, button=button)
                    self.log(f"🖱 Mouse down na posição ({x},{y}) - Botão: {button}")
                elif click_action == "up":
                    pyautogui.mouseUp(x, y, button=button)
                    self.log(f"🖱 Mouse up na posição ({x},{y}) - Botão: {button}")
                else:  # normal
                    clicks = options.get("clicks", 1)
                    hold_time = options.get("hold_time", 0)

                    if hold_time > 0:
                        pyautogui.mouseDown(x, y, button=button)
                        time.sleep(hold_time)
                        pyautogui.mouseUp(x, y, button=button)
                        self.log(f"🖱 Segurou clique por {hold_time}s na posição ({x},{y})")
                    else:
                        pyautogui.click(x, y, clicks=clicks, button=button)
                        self.log(f"✓ Clicou na posição atual ({x},{y})")

                    self.stats["clicks"] += clicks

                return True
            
            # CLICK ALL - REMOVIDO
            
            # CLICK FOLDER (clica em todas as imagens de uma pasta)
            elif tipo == "click_folder":
                if not os.path.exists(value):
                    self.log(f"✗ Pasta não encontrada: {value}", "WARN")
                    return False

                click_mode = options.get("click_mode", "fixed")
                click_action = options.get("click_action", "normal")  # normal, down, up
                radius = options.get("click_radius", 5)
                button = options.get("button", "left")
                clicks_total = 0

                # Carrega todas as imagens da pasta
                for file in os.listdir(value):
                    if file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                        img_path = os.path.join(value, file)
                        try:
                            img = cv2.imread(img_path)
                            if img is not None:
                                pos, confidence = self.find_image(img)
                                if pos:
                                    x, y = pos

                                    if click_mode == "variable":
                                        offset_x = np.random.randint(-radius, radius + 1)
                                        offset_y = np.random.randint(-radius, radius + 1)
                                        x += offset_x
                                        y += offset_y

                                    if click_action == "down":
                                        pyautogui.mouseDown(x, y, button=button)
                                        self.log(f"🖱 Mouse down em {file} ({x},{y}) - Botão: {button}")
                                        clicks_total += 1
                                    elif click_action == "up":
                                        pyautogui.mouseUp(x, y, button=button)
                                        self.log(f"🖱 Mouse up em {file} ({x},{y}) - Botão: {button}")
                                        clicks_total += 1
                                    else:  # normal
                                        pyautogui.click(x, y, button=button)
                                        self.log(f"✓ Clicou em {file} ({x},{y})")
                                        clicks_total += 1

                                    time.sleep(0.2)
                        except Exception as e:
                            self.log(f"⚠ Erro ao processar {file}: {e}", "WARN")

                self.log(f"✓ Total: {clicks_total} ações em imagens da pasta")
                return True
            
            # DELAY (comando dedicado)
            elif tipo == "delay":
                delay = float(value)
                self.log(f"⏱ Delay: {delay}s")
                time.sleep(delay)
                return True
            
            # WAIT FOR IMAGE
            elif tipo == "wait_image":
                timeout = options.get("timeout", 10)
                start = time.time()
                
                while time.time() - start < timeout:
                    if not self.running:
                        return False
                    
                    if value in self.targets_cache:
                        pos, _ = self.find_image(self.targets_cache[value])
                        if pos:
                            self.log(f"✓ Imagem {value} apareceu!")
                            return True
                    
                    time.sleep(0.5)
                
                self.log(f"✗ Timeout aguardando {value}", "WARN")
                return False
            
            # KEYBOARD
            elif tipo == "key":
                key_action = options.get("key_action", "normal")  # normal, down, up, hold
                hold_time = options.get("hold_time", 0)

                if key_action == "down":
                    keyboard.press(value)
                    self.log(f"⌨ Tecla pressionada: {value}")
                elif key_action == "up":
                    keyboard.release(value)
                    self.log(f"⌨ Tecla liberada: {value}")
                elif key_action == "hold":
                    # Segura a tecla pelo tempo especificado
                    keyboard.press(value)
                    time.sleep(hold_time)
                    keyboard.release(value)
                    self.log(f"⌨ SEGUROU tecla {value} por {hold_time}s")
                else:  # normal
                    if hold_time > 0 and hold_time >= 1.0:
                        # Se tiver hold_time >= 1s, considera como hold
                        keyboard.press(value)
                        time.sleep(hold_time)
                        keyboard.release(value)
                        self.log(f"⌨ Segurou tecla {value} por {hold_time}s")
                    else:
                        # Pressiona e solta rapidamente
                        keyboard.press_and_release(value)
                        self.log(f"⌨ Tecla: {value}")

                self.stats["keys_pressed"] += 1
                return True
            
            elif tipo == "type_text":
                interval = options.get("interval", 0.05)
                keyboard.write(value, delay=interval)
                self.log(f"⌨ Digitou: {value}")
                return True
            
            # MOUSE
            elif tipo == "move_mouse":
                x, y = map(int, value.split(","))
                duration = options.get("duration", 0.5)
                pyautogui.moveTo(x, y, duration=duration)
                self.log(f"🖱 Moveu mouse para ({x},{y})")
                return True
            
            elif tipo == "click_pos":
                x, y = map(int, value.split(","))
                click_mode = options.get("click_mode", "fixed")
                click_action = options.get("click_action", "normal")  # normal, down, up

                if click_mode == "variable":
                    radius = options.get("click_radius", 5)
                    offset_x = np.random.randint(-radius, radius + 1)
                    offset_y = np.random.randint(-radius, radius + 1)
                    x += offset_x
                    y += offset_y

                button = options.get("button", "left")

                if click_action == "down":
                    pyautogui.mouseDown(x, y, button=button)
                    self.log(f"🖱 Mouse down em ({x},{y}) - Botão: {button}")
                elif click_action == "up":
                    pyautogui.mouseUp(x, y, button=button)
                    self.log(f"🖱 Mouse up em ({x},{y}) - Botão: {button}")
                else:  # normal
                    clicks = options.get("clicks", 1)
                    hold_time = options.get("hold_time", 0)

                    if hold_time > 0:
                        pyautogui.mouseDown(x, y, button=button)
                        time.sleep(hold_time)
                        pyautogui.mouseUp(x, y, button=button)
                        self.log(f"🖱 Segurou clique por {hold_time}s em ({x},{y})")
                    else:
                        pyautogui.click(x, y, clicks=clicks, button=button)
                        self.log(f"🖱 Clicou em ({x},{y})")

                    self.stats["clicks"] += clicks

                return True
            
            elif tipo == "drag":
                # Nova estrutura: coordenadas separadas no comando
                start_x = cmd.get('start_x')
                start_y = cmd.get('start_y')
                end_x = cmd.get('end_x')
                end_y = cmd.get('end_y')
                button = cmd.get('button', 'left')
                
                # Converte para inteiros se necessário
                try:
                    x1 = int(start_x)
                    y1 = int(start_y)
                    x2 = int(end_x)
                    y2 = int(end_y)
                except (ValueError, TypeError):
                    self.log(f"✗ Coordenadas inválidas para drag: {start_x},{start_y} -> {end_x},{end_y}", "ERROR")
                    return False
                
                duration = options.get("duration", 0.5)
                pyautogui.moveTo(x1, y1)
                pyautogui.drag(x2-x1, y2-y1, duration=duration, button=button)
                self.log(f"🖱 Arraste de ({x1},{y1}) para ({x2},{y2}) - Botão: {button}")
                return True
            
            elif tipo == "scroll":
                amount = int(value)
                pyautogui.scroll(amount)
                self.log(f"🖱 Scroll: {amount}")
                return True
            
            # OCR
            elif tipo == "find_text":
                found = self.find_text_ocr(value)
                if found:
                    self.log(f"✓ Texto encontrado: {value}")
                else:
                    self.log(f"✗ Texto não encontrado: {value}", "WARN")
                return found
            
            elif tipo == "comment":
                self.log(f"💬 {value}", "INFO")
                return True
            
            # STOP (parar macro com validação)
            elif tipo == "stop":
                stop_type = options.get("stop_type", "image")  # image ou text
                
                if stop_type == "image":
                    # Para quando a imagem for encontrada
                    if value in self.targets_cache:
                        pos, confidence = self.find_image(self.targets_cache[value])
                        if pos:
                            self.log(f"⏹ Imagem {value} encontrada! Parando macro...", "SUCCESS")
                            self.stop()
                            return True
                        else:
                            self.log(f"✓ Imagem {value} não encontrada, continuando...", "INFO")
                elif stop_type == "text":
                    # Para quando o texto for encontrado - usa OCR avançado
                    use_advanced = options.get("ocr_advanced", True)
                    if use_advanced:
                        found = self.find_text_ocr_advanced(value)
                    else:
                        found = self.find_text_ocr(value)
                    
                    if found:
                        self.log(f"⏹ Texto '{value}' encontrado! Parando macro...", "SUCCESS")
                        self.stop()
                        return True
                    else:
                        self.log(f"✓ Texto '{value}' não encontrado, continuando...", "INFO")
                
                return True
            
            # Blocos de controle SE/SENAO/FIM são processados no run()
            elif tipo in ["se", "senao", "fim"]:
                # Esses tipos são tratados em process_se_senao
                return True
            
        except Exception as e:
            self.log(f"❌ Erro ao executar {tipo}: {e}", "ERROR")
            self.stats["errors"] += 1
            return False
        
        return True
    
    def process_se_senao(self, commands, start_idx):
        """
        Processa blocos de SE/SENAO/FIM (IF/ELSE/END)
        Retorna: (bloco_if_commands, bloco_else_commands, idx_proximo_apos_fim)
        
        Estrutura esperada:
        [start_idx] -> "se" (condição)
        [start_idx+1] -> comandos do IF
        ...
        [idx_senao] -> "senao"
        [idx_senao+1] -> comandos do ELSE
        ...
        [idx_fim] -> "fim"
        """
        if_commands = []
        else_commands = []
        idx = start_idx + 1
        
        # Coleta comandos até encontrar "senao" ou "fim"
        while idx < len(commands):
            cmd = commands[idx]
            if cmd.get("type") == "senao":
                # Encontrou o senao, passa para coletar comandos do else
                idx += 1
                break
            if cmd.get("type") == "fim":
                # Bloco sem else, salta direto
                return if_commands, [], idx + 1
            if_commands.append(commands[idx])
            idx += 1
        
        # Coleta comandos após "senao" até encontrar "fim"
        while idx < len(commands):
            cmd = commands[idx]
            if cmd.get("type") == "fim":
                # Encontrou fim, retorna
                return if_commands, else_commands, idx + 1
            else_commands.append(commands[idx])
            idx += 1
        
        # Se não encontrou fim, retorna o que coletou até o fim da lista
        return if_commands, else_commands, idx
    
    def execute_se_senao_block(self, se_cmd, if_commands, else_commands):
        """
        Executa um bloco SE/SENAO
        - Avalia a condição do SE
        - Se verdadeira: executa if_commands
        - Se falsa: executa else_commands
        """
        condition_value = se_cmd.get("value", "")
        options = se_cmd.get("options", {})
        
        # Avalia a condição
        condition_result = False
        condition_type = options.get("condition_type", "image")  # image, multi_image, text
        
        if condition_type == "image":
            # Verifica se a imagem foi encontrada
            if condition_value in self.targets_cache:
                pos, confidence = self.find_image(self.targets_cache[condition_value])
                condition_result = pos is not None
                self.log(f"🔍 SE: Procurando imagem '{condition_value}' -> {'✓ Encontrada' if condition_result else '✗ Não encontrada'}")
        
        elif condition_type == "multi_image":
            # Verifica se qualquer uma das imagens da pasta foi encontrada
            folder_path = condition_value
            if os.path.exists(folder_path):
                images = [f for f in os.listdir(folder_path) 
                         if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
                self.log(f"🔍 SE: Procurando qualquer uma de {len(images)} imagens da pasta...")
                
                # Carrega imagens da pasta no cache temporariamente
                for image_file in images:
                    image_path = os.path.join(folder_path, image_file)
                    try:
                        img = cv2.imread(image_path)
                        if img is not None:
                            pos, confidence = self.find_image(img)
                            if pos is not None:
                                condition_result = True
                                self.log(f"✓ Imagem encontrada: '{image_file}'")
                                break
                    except Exception as e:
                        self.log(f"✗ Erro ao processar '{image_file}': {e}", "ERROR")
                
                if not condition_result:
                    self.log(f"✗ Nenhuma imagem da pasta foi encontrada")
            else:
                self.log(f"✗ Pasta não encontrada: {folder_path}", "ERROR")
        
        elif condition_type == "text":
            # Verifica se o texto foi encontrado - usa OCR avançado
            condition_result = self.find_text_ocr_advanced(condition_value)
            self.log(f"🔍 SE: Procurando texto '{condition_value}' -> {'✓ Encontrado' if condition_result else '✗ Não encontrado'}")
        
        # Seleciona qual bloco executar
        commands_to_execute = if_commands if condition_result else else_commands
        
        if condition_result:
            self.log(f"✅ Condição VERDADEIRA - Executando bloco SE", "SUCCESS")
        else:
            self.log(f"❌ Condição FALSA - Executando bloco SENAO", "SUCCESS")
        
        # Executa os comandos do bloco apropriado
        results = []
        for cmd in commands_to_execute:
            if not self.running:
                break
            
            result = self.execute_command(cmd)
            results.append(result)
            
            # Delay customizado
            custom_delay = cmd.get("delay", 0)
            if custom_delay > 0:
                time.sleep(custom_delay)
            
            # Delay global
            time.sleep(self.config.data["delay_global"])
        
        return results

    def run(self):
        """Loop principal do bot"""
        self.running = True
        self.stats["start_time"] = time.time()
        self.stats["executions"] = 0
        
        self.log("🚀 Bot iniciado!", "SUCCESS")
        
        # Delay inicial configurável
        initial_delay = self.config.data.get("initial_delay", 3.0)
        if initial_delay > 0:
            self.log(f"⏳ Aguardando {initial_delay}s antes de iniciar...", "INFO")
            time.sleep(initial_delay)
        
        self.load_targets()
        
        loop_count = 0
        max_loops = self.config.data.get("loop_count", 1)
        
        while self.running:
            i = 0
            while i < len(self.commands):
                if not self.running:
                    break
                
                cmd = self.commands[i]
                
                # Processa bloco SE/SENAO
                if cmd.get("type") == "se":
                    if_commands, else_commands, next_idx = self.process_se_senao(self.commands, i)
                    self.execute_se_senao_block(cmd, if_commands, else_commands)
                    i = next_idx  # Pula para próximo comando após bloco
                    continue
                
                # Executa comando normal
                self.execute_command(cmd)
                
                # Delay customizado
                custom_delay = cmd.get("delay", 0)
                if custom_delay > 0:
                    time.sleep(custom_delay)
                
                # Delay global
                time.sleep(self.config.data["delay_global"])
                
                i += 1
            
            self.stats["executions"] += 1
            loop_count += 1
            
            # Verifica modo de loop
            if self.config.data["loop_mode"] == "once":
                break
            elif self.config.data["loop_mode"] == "count" and loop_count >= max_loops:
                self.log(f"✓ Completou {loop_count} repetições", "SUCCESS")
                break
            
            time.sleep(self.config.data["delay_between_actions"])
        
        self.running = False
        elapsed = time.time() - self.stats["start_time"]
        self.log(f"⏹ Bot parado! Tempo: {elapsed:.1f}s | Execuções: {self.stats['executions']}", "SUCCESS")
    
    def start(self):
        if not self.running:
            threading.Thread(target=self.run, daemon=True).start()
    
    def stop(self):
        self.running = False

# ==================== INTERFACE GRÁFICA ====================
class ModernUI:
    def __init__(self):
        self.bot = MacroBot()
        self.bot.log_callback = self.add_log
        self._loading = False  # Flag para evitar duplicação
        self.clipboard_command = None  # Armazena comando para copiar/colar
        self.clipboard_is_multiple = False  # Flag para indicar se é múltiplo
        self.recording = False  # Flag de gravação
        self.recorded_commands = []  # Comandos gravados
        self.last_record_time = None  # Tempo do último comando gravado
        self.mouse_press_times = {}  # Armazena tempo de pressão dos botões do mouse
        self.key_press_times = {}  # Armazena tempo de pressão das teclas
        
        # Dicionário de tradução de comandos
        self.cmd_display = {
            "🖱️ Clicar em Imagem": "click_image",
            "🖱️ Clicar em Várias Imagens (Pasta)": "click_folder",
            "🖱️ Apenas Clicar": "click",
            "🔀 SE (Condição)": "se",
            "🔚 SENAO": "senao",
            "🏁 FIM": "fim",
            "⌨️ Pressionar Tecla": "key",
            "⌨️ Digitar Texto": "type_text",
            "🖱️ Mover Mouse": "move_mouse",
            "🖱️ Clicar em Posição": "click_pos",
            "🖱️ Arrastar": "drag",
            "🖱️ Rolar (Scroll)": "scroll",
            "🔍 Buscar Texto (OCR)": "find_text",
            "⏹ Parar (Validação)": "stop",
            "⏱️ Delay": "delay",
            "💬 Comentário": "comment"
        }
        
        # Lista de teclas disponíveis
        self.available_keys = [
            "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
            "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
            "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
            "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
            "enter", "space", "tab", "esc", "backspace", "delete",
            "home", "end", "pageup", "pagedown",
            "up", "down", "left", "right",
            "shift", "ctrl", "alt", "win",
            "num0", "num1", "num2", "num3", "num4", "num5", "num6", "num7", "num8", "num9",
            "num+", "num-", "num*", "num/", "num.", "num_lock"
        ]
        
        self.root = tk.Tk()
        self.root.title(f"GDMmacrobot v{VERSION}")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1a1a2e")
        
        # Configurar ícone da janela
        self.load_window_icon()
        
        # Cores do tema escuro
        self.colors = {
            "bg": "#1a1a2e",
            "bg_light": "#16213e",
            "accent": "#0f3460",
            "primary": "#e94560",
            "success": "#06ffa5",
            "warning": "#ffd93d",
            "danger": "#dc3545",
            "text": "#f1f1f1",
            "text_dim": "#a0a0a0"
        }
        
        self.setup_styles()
        self.create_widgets()
        self.adjust_window_size()
        self.setup_hotkeys()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Configurar estilos
        style.configure("Dark.TFrame", background=self.colors["bg"])
        style.configure("Card.TFrame", background=self.colors["bg_light"])
        style.configure("Dark.TLabel", background=self.colors["bg"], foreground=self.colors["text"])
        style.configure("Title.TLabel", background=self.colors["bg"], foreground=self.colors["success"], font=("Arial", 16, "bold"))
        style.configure("Dark.TButton", background=self.colors["accent"], foreground=self.colors["text"])
        
    def load_logo_image(self):
        """Carrega a imagem do logo se existir"""
        try:
            # Tenta carregar logo.png da pasta do programa
            logo_path = get_resource_path("logo.png")
            if os.path.exists(logo_path):
                image = Image.open(logo_path)
                # Redimensiona para um tamanho apropriado (altura 60px, mantendo proporção)
                aspect_ratio = image.width / image.height
                new_height = 60
                new_width = int(new_height * aspect_ratio)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(image)
            else:
                return None
        except Exception as e:
            print(f"Erro ao carregar logo: {e}")
            return None
    
    def load_window_icon(self):
        """Carrega o ícone da janela se existir"""
        try:
            # Tenta carregar icon.ico ou icon.png da pasta do programa
            icon_paths = [
                get_resource_path("icon.ico"),
                get_resource_path("icon.png")
            ]
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    # Para .ico, usa diretamente
                    if icon_path.endswith('.ico'):
                        self.root.iconbitmap(icon_path)
                        print(f"Ícone carregado: {icon_path}")
                        return
                    # Para .png, converte para PhotoImage e usa iconphoto
                    elif icon_path.endswith('.png'):
                        icon_image = tk.PhotoImage(file=icon_path)
                        self.root.iconphoto(True, icon_image)
                        print(f"Ícone carregado: {icon_path}")
                        return
            
            print("Nenhum arquivo de ícone encontrado (icon.ico ou icon.png)")
        except Exception as e:
            print(f"Erro ao carregar ícone: {e}")
        
    def adjust_window_size(self):
        """Ajusta automaticamente o tamanho da janela para se adequar ao conteúdo"""
        try:
            # Atualiza a interface para calcular os tamanhos corretos
            self.root.update_idletasks()
            
            # Obtém o tamanho necessário para todos os widgets
            required_width = self.root.winfo_reqwidth()
            required_height = self.root.winfo_reqheight()
            
            # Define um tamanho mínimo para evitar janelas muito pequenas
            min_width = 1200
            min_height = 800
            
            # Usa o maior valor entre o tamanho necessário e o mínimo
            final_width = max(required_width, min_width)
            final_height = max(required_height, min_height)
            
            # Aplica a geometria ajustada
            self.root.geometry(f"{final_width}x{final_height}")
            
            # Centraliza a janela na tela
            self.center_window(final_width, final_height)
            
        except Exception as e:
            print(f"Erro ao ajustar tamanho da janela: {e}")
            # Fallback para o tamanho padrão
            self.root.geometry("1200x800")
    
    def center_window(self, width, height):
        """Centraliza a janela na tela"""
        try:
            # Obtém o tamanho da tela
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # Calcula a posição para centralizar
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            
            # Garante que a posição não seja negativa
            x = max(0, x)
            y = max(0, y)
            
            # Aplica a geometria com posição centralizada
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            
        except Exception as e:
            print(f"Erro ao centralizar janela: {e}")
    
    def position_dialog_window(self, dialog_window):
        """Posiciona a janela de diálogo no mesmo local da interface principal"""
        try:
            dialog_window.update_idletasks()
            
            # Obtém a posição e tamanho da janela principal
            main_x = self.root.winfo_x()
            main_y = self.root.winfo_y()
            main_width = self.root.winfo_width()
            main_height = self.root.winfo_height()
            
            # Obtém o tamanho da janela de diálogo
            dialog_width = dialog_window.winfo_reqwidth()
            dialog_height = dialog_window.winfo_reqheight()
            
            # Calcula a posição para centralizar o diálogo em relação à janela principal
            x = main_x + (main_width - dialog_width) // 2
            y = main_y + (main_height - dialog_height) // 2
            
            # Garante que a posição não seja negativa
            x = max(0, x)
            y = max(0, y)
            
            # Aplica a posição
            dialog_window.geometry(f"+{x}+{y}")
            
        except Exception as e:
            # Se houver erro, deixa na posição padrão
            pass
        
    def create_widgets(self):
        # Container principal
        main = ttk.Frame(self.root, style="Dark.TFrame")
        main.pack(fill="both", expand=True, padx=10, pady=10)
        
        # ===== TOPO =====
        top_frame = ttk.Frame(main, style="Dark.TFrame")
        top_frame.pack(fill="x", pady=(0, 10))
        
        # Carrega e exibe o logo
        self.logo_image = self.load_logo_image()
        if self.logo_image:
            logo_label = tk.Label(top_frame, image=self.logo_image, bg=self.colors["bg"])
            logo_label.pack(side="left")
        else:
            # Fallback para texto se não houver imagem
            ttk.Label(top_frame, text="⚡ GDMmacrobot", style="Title.TLabel").pack(side="left")
        
        # Label de versão (à esquerda, após o logo)
        version_label = tk.Label(top_frame, text=f"v{VERSION}", 
                                bg=self.colors["bg"], fg=self.colors["text_dim"],
                                font=("Arial", 9))
        version_label.pack(side="left", padx=(10, 0))
        
        # Botões de controle
        ctrl_frame = tk.Frame(top_frame, bg=self.colors["bg"])
        ctrl_frame.pack(side="right")
        
        # Frame para botões e hotkeys
        buttons_info_frame = tk.Frame(ctrl_frame, bg=self.colors["bg"])
        buttons_info_frame.pack(side="left", padx=5)
        
        self.btn_start = tk.Button(buttons_info_frame, text="▶ INICIAR", command=self.toggle_bot,
                                   bg="#06ffa5", fg="#000", font=("Arial", 11, "bold"),
                                   padx=20, pady=8, relief="flat", cursor="hand2")
        self.btn_start.pack(side="top")
        
        start_hotkey_label = tk.Label(buttons_info_frame, text="(F9)", bg=self.colors["bg"],
                                      fg=self.colors["text_dim"], font=("Arial", 8))
        start_hotkey_label.pack(side="top")
        
        # Frame para outros botões
        other_btns_frame = tk.Frame(ctrl_frame, bg=self.colors["bg"])
        other_btns_frame.pack(side="left", padx=5)
        
        # Record
        record_frame = tk.Frame(other_btns_frame, bg=self.colors["bg"])
        record_frame.pack(side="left", padx=2)
        
        self.btn_record = tk.Button(record_frame, text="⏺ GRAVAR", command=self.toggle_record,
                                   bg="#ff6b6b", fg="#fff", font=("Arial", 11, "bold"),
                                   padx=20, pady=8, relief="flat", cursor="hand2")
        self.btn_record.pack(side="top")
        
        record_hotkey_label = tk.Label(record_frame, text="(F5)", bg=self.colors["bg"],
                                      fg=self.colors["text_dim"], font=("Arial", 8))
        record_hotkey_label.pack(side="top")
        
        # Config
        config_btn_frame = tk.Frame(other_btns_frame, bg=self.colors["bg"])
        config_btn_frame.pack(side="left", padx=2)
        
        self.btn_settings = tk.Button(config_btn_frame, text="⚙ CONFIG", command=self.open_settings,
                                     bg="#6c5ce7", fg="#fff", font=("Arial", 11, "bold"),
                                     padx=20, pady=8, relief="flat", cursor="hand2")
        self.btn_settings.pack(side="top")
        
        settings_hotkey_label = tk.Label(config_btn_frame, text="", bg=self.colors["bg"],
                                        fg=self.colors["text_dim"], font=("Arial", 8))
        settings_hotkey_label.pack(side="top")
        
        # Update
        update_btn_frame = tk.Frame(other_btns_frame, bg=self.colors["bg"])
        update_btn_frame.pack(side="left", padx=2)
        
        self.btn_update = tk.Button(update_btn_frame, text="🔄 ATUALIZAR", command=self.check_updates,
                                   bg="#ffa502", fg="#fff", font=("Arial", 11, "bold"),
                                   padx=20, pady=8, relief="flat", cursor="hand2")
        self.btn_update.pack(side="top")
        
        update_hotkey_label = tk.Label(update_btn_frame, text="", bg=self.colors["bg"],
                                      fg=self.colors["text_dim"], font=("Arial", 8))
        update_hotkey_label.pack(side="top")
        
        # ===== CONTEÚDO DIVIDIDO =====
        content = ttk.Frame(main, style="Dark.TFrame")
        content.pack(fill="both", expand=True)
        
        # ESQUERDA - Comandos
        left_panel = ttk.Frame(content, style="Card.TFrame")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        self.create_commands_panel(left_panel)
        
        # DIREITA - Config e Log
        right_panel = ttk.Frame(content, style="Dark.TFrame")
        right_panel.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        self.create_config_panel(right_panel)
        self.create_log_panel(right_panel)
        
    def create_commands_panel(self, parent):
        ttk.Label(parent, text="📋 COMANDOS", style="Title.TLabel").pack(pady=10)
        
        # Lista de comandos
        list_frame = tk.Frame(parent, bg=self.colors["bg_light"])
        list_frame.pack(fill="both", expand=True, padx=10)
        
        scrollbar = tk.Scrollbar(list_frame, bg=self.colors["accent"])
        scrollbar.pack(side="right", fill="y")
        
        # Criar Treeview (tabela)
        style = ttk.Style()
        style.configure("Commands.Treeview",
                       background="#0f3460",
                       foreground="#ffffff",
                       fieldbackground="#0f3460",
                       font=("Consolas", 11),
                       rowheight=28)
        style.configure("Commands.Treeview.Heading",
                       background="#1a1a2e",
                       foreground="#06ffa5",
                       font=("Consolas", 11, "bold"))
        style.map("Commands.Treeview",
                 background=[("selected", "#16213e")],
                 foreground=[("selected", "#06ffa5")])
        
        self.cmd_listbox = ttk.Treeview(list_frame, 
                                        columns=("num", "comando", "valor", "delay"),
                                        show="headings",
                                        yscrollcommand=scrollbar.set,
                                        style="Commands.Treeview",
                                        selectmode="extended")
        
        # Definir cabeçalhos
        self.cmd_listbox.heading("num", text="Nº")
        self.cmd_listbox.heading("comando", text="COMANDO")
        self.cmd_listbox.heading("valor", text="VALOR/TECLA")
        self.cmd_listbox.heading("delay", text="DELAY")
        
        # Definir largura das colunas com stretch
        self.cmd_listbox.column("num", width=40, minwidth=40, stretch=False, anchor="center")
        self.cmd_listbox.column("comando", width=160, minwidth=100, stretch=True, anchor="w")
        self.cmd_listbox.column("valor", width=400, minwidth=200, stretch=True, anchor="w")
        self.cmd_listbox.column("delay", width=70, minwidth=60, stretch=False, anchor="center")
        
        # Configurar tags de cores para diferentes tipos de comandos
        self.cmd_listbox.tag_configure("click", foreground="#06ffa5")  # Verde - Cliques
        self.cmd_listbox.tag_configure("key", foreground="#ffd700")  # Dourado - Teclas
        self.cmd_listbox.tag_configure("key_down", foreground="#ff6b6b")  # Vermelho - Pressionar
        self.cmd_listbox.tag_configure("key_up", foreground="#ff9999")  # Rosa - Liberar
        self.cmd_listbox.tag_configure("control", foreground="#00d4ff")  # Ciano - Controle
        self.cmd_listbox.tag_configure("delay", foreground="#a78bfa")  # Roxo - Delay
        self.cmd_listbox.tag_configure("other", foreground="#b8b8b8")  # Cinza - Outros
        
        self.cmd_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.cmd_listbox.yview)
        
        # Variáveis para drag and drop
        self.drag_item = None
        self.drag_start_index = None
        
        # Adiciona método curselection para compatibilidade
        def treeview_curselection():
            selection = self.cmd_listbox.selection()
            if selection:
                # Retorna tupla com todos os índices selecionados
                indices = tuple(self.cmd_listbox.index(item) for item in selection)
                return indices
            return ()
        
        self.cmd_listbox.curselection = treeview_curselection
        
        # Binds para drag and drop
        self.cmd_listbox.bind("<ButtonPress-1>", self.on_drag_start)
        self.cmd_listbox.bind("<B1-Motion>", self.on_drag_motion)
        self.cmd_listbox.bind("<ButtonRelease-1>", self.on_drag_release)
        
        self.cmd_listbox.bind("<Double-1>", self.edit_command_from_treeview)
        self.cmd_listbox.bind("<Delete>", self.delete_command_from_treeview)
        self.cmd_listbox.bind("<Control-c>", self.copy_command_shortcut)
        self.cmd_listbox.bind("<Control-v>", self.paste_command_shortcut)
        self.cmd_listbox.bind("<Button-3>", self.show_context_menu)
        
        # Botões de ação
        btn_frame = tk.Frame(parent, bg=self.colors["bg_light"])
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Button(btn_frame, text="➕ Adicionar", command=self.add_command_dialog,
                 bg=self.colors["success"], fg="#000", font=("Arial", 9, "bold"),
                 padx=15, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=2)
        
        tk.Button(btn_frame, text="🗑️ Excluir", command=self.delete_command_button,
                 bg=self.colors["danger"], fg="#fff", font=("Arial", 9, "bold"),
                 padx=15, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=2)
        
        tk.Button(btn_frame, text="⬆️ Mover Acima", command=self.move_command_up,
                 bg=self.colors["accent"], fg="#fff", font=("Arial", 9, "bold"),
                 padx=15, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=2)
        
        tk.Button(btn_frame, text="⬇️ Mover Abaixo", command=self.move_command_down,
                 bg=self.colors["accent"], fg="#fff", font=("Arial", 9, "bold"),
                 padx=15, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=2)
        
        tk.Button(btn_frame, text="📋 Copiar", command=self.copy_command,
                 bg=self.colors["accent"], fg="#fff", font=("Arial", 9, "bold"),
                 padx=15, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=2)
        
        tk.Button(btn_frame, text="📌 Colar", command=self.paste_command,
                 bg=self.colors["accent"], fg="#fff", font=("Arial", 9, "bold"),
                 padx=15, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=2)
        
        # Segundo frame de botões
        btn_frame2 = tk.Frame(parent, bg=self.colors["bg_light"])
        btn_frame2.pack(fill="x", padx=10, pady=(0, 10))
        
        tk.Button(btn_frame2, text="💾 Salvar", command=self.save_commands,
                 bg=self.colors["accent"], fg="#fff", font=("Arial", 9, "bold"),
                 padx=15, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=2)
        
        tk.Button(btn_frame2, text="📂 Carregar", command=self.load_commands,
                 bg=self.colors["accent"], fg="#fff", font=("Arial", 9, "bold"),
                 padx=15, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=2)
        
        tk.Button(btn_frame2, text="🗑 Limpar", command=self.clear_commands,
                 bg="#5a5a5a", fg="#fff", font=("Arial", 9, "bold"),
                 padx=15, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=2)
    
    def create_config_panel(self, parent):
        config_card = ttk.Frame(parent, style="Card.TFrame")
        config_card.pack(fill="x", pady=(0, 10))
        
        ttk.Label(config_card, text="⚙ CONFIGURAÇÕES", style="Title.TLabel").pack(pady=10)
        
        # Grid de configs
        grid = tk.Frame(config_card, bg=self.colors["bg_light"])
        grid.pack(fill="x", padx=15, pady=5)
        
        # Pasta de imagens
        tk.Label(grid, text="Pasta:", bg=self.colors["bg_light"], fg=self.colors["text"]).grid(row=0, column=0, sticky="w", pady=5)
        self.folder_var = tk.StringVar(value=self.bot.config.data["folder"])
        tk.Entry(grid, textvariable=self.folder_var, bg="#0f3460", fg=self.colors["text"],
                relief="flat", width=25).grid(row=0, column=1, padx=5)
        tk.Button(grid, text="📁", command=self.select_folder, bg=self.colors["accent"],
                 fg=self.colors["text"], relief="flat", cursor="hand2").grid(row=0, column=2)
        
        # Sensibilidade
        tk.Label(grid, text="Sensibilidade:", bg=self.colors["bg_light"], fg=self.colors["text"]).grid(row=1, column=0, sticky="w", pady=5)
        self.threshold_var = tk.DoubleVar(value=self.bot.config.data["threshold"])
        tk.Scale(grid, from_=0.5, to=1.0, resolution=0.05, orient="horizontal",
                variable=self.threshold_var, bg=self.colors["bg_light"],
                fg=self.colors["text"], highlightthickness=0, length=200).grid(row=1, column=1, columnspan=2)
        
        # Delay global
        tk.Label(grid, text="Delay Global:", bg=self.colors["bg_light"], fg=self.colors["text"]).grid(row=2, column=0, sticky="w", pady=5)
        self.delay_var = tk.DoubleVar(value=self.bot.config.data["delay_global"])
        tk.Scale(grid, from_=0.0, to=2.0, resolution=0.1, orient="horizontal",
                variable=self.delay_var, bg=self.colors["bg_light"],
                fg=self.colors["text"], highlightthickness=0, length=200).grid(row=2, column=1, columnspan=2)
        
        # Delay inicial
        tk.Label(grid, text="Delay Inicial:", bg=self.colors["bg_light"], fg=self.colors["text"]).grid(row=3, column=0, sticky="w", pady=5)
        self.initial_delay_var = tk.DoubleVar(value=self.bot.config.data.get("initial_delay", 3.0))
        tk.Scale(grid, from_=0.0, to=10.0, resolution=0.5, orient="horizontal",
                variable=self.initial_delay_var, bg=self.colors["bg_light"],
                fg=self.colors["text"], highlightthickness=0, length=200).grid(row=3, column=1, columnspan=2)
        
        # Loop mode
        tk.Label(grid, text="Modo:", bg=self.colors["bg_light"], fg=self.colors["text"]).grid(row=4, column=0, sticky="w", pady=5)
        self.loop_var = tk.StringVar(value=self.bot.config.data["loop_mode"])
        loop_frame = tk.Frame(grid, bg=self.colors["bg_light"])
        loop_frame.grid(row=4, column=1, columnspan=2, sticky="w")
        tk.Radiobutton(loop_frame, text="Infinito", variable=self.loop_var, value="infinite",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"], command=self.toggle_loop_count).pack(side="left", padx=5)
        tk.Radiobutton(loop_frame, text="Uma vez", variable=self.loop_var, value="once",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"], command=self.toggle_loop_count).pack(side="left")
        tk.Radiobutton(loop_frame, text="Repetir X vezes", variable=self.loop_var, value="count",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"], command=self.toggle_loop_count).pack(side="left", padx=5)
        
        # Quantidade de repetições
        tk.Label(grid, text="Repetições:", bg=self.colors["bg_light"], fg=self.colors["text"]).grid(row=5, column=0, sticky="w", pady=5)
        self.loop_count_var = tk.IntVar(value=self.bot.config.data.get("loop_count", 1))
        self.loop_count_entry = tk.Entry(grid, textvariable=self.loop_count_var, bg="#0f3460", 
                                         fg=self.colors["text"], relief="flat", width=10)
        self.loop_count_entry.grid(row=5, column=1, sticky="w", padx=5)
        
        # Desabilita se não for modo count
        if self.loop_var.get() != "count":
            self.loop_count_entry.config(state="disabled")
        
        # Botão salvar config
        tk.Button(config_card, text="💾 Salvar Configurações", command=self.save_config,
                 bg=self.colors["accent"], fg=self.colors["text"], font=("Arial", 9, "bold"),
                 padx=20, pady=8, relief="flat", cursor="hand2").pack(pady=10)
    
    def create_log_panel(self, parent):
        log_card = ttk.Frame(parent, style="Card.TFrame")
        log_card.pack(fill="both", expand=True)
        
        ttk.Label(log_card, text="📊 LOG", style="Title.TLabel").pack(pady=10)
        
        log_frame = tk.Frame(log_card, bg=self.colors["bg_light"])
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        scrollbar = tk.Scrollbar(log_frame, bg=self.colors["accent"])
        scrollbar.pack(side="right", fill="y")
        
        self.log_text = tk.Text(log_frame, yscrollcommand=scrollbar.set,
                               bg="#0a0a0a", fg="#00ff00", font=("Consolas", 9),
                               relief="flat", highlightthickness=0, state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Tags de cores
        self.log_text.tag_config("INFO", foreground="#00ff00")
        self.log_text.tag_config("SUCCESS", foreground="#06ffa5")
        self.log_text.tag_config("WARN", foreground="#ffd93d")
        self.log_text.tag_config("ERROR", foreground="#e94560")
        
    def add_log(self, message, level="INFO"):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n", level)
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        
    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")
    
    def delete_command(self, event):
        selection = self.cmd_listbox.curselection()
        if not selection:
            return
        
        # Suporta múltipla seleção
        if len(selection) == 1:
            msg = "Remover este comando?"
        else:
            msg = f"Remover {len(selection)} comandos?"
        
        if messagebox.askyesno("Confirmar", msg):
            # Deleta em ordem reversa para evitar mudança de índices
            for idx in sorted(selection, reverse=True):
                del self.bot.commands[idx]
            self.refresh_command_list()
    
    def delete_command_button(self):
        """Excluir comando via botão (sem evento)"""
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível deletar comandos enquanto o macro está rodando!\nPause o macro primeiro.")
            return
        
        selection = self.cmd_listbox.curselection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um ou mais comandos para excluir!")
            return
        
        self.delete_command(None)
    
    def clear_commands(self):
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível limpar comandos enquanto o macro está rodando!\nPause o macro primeiro.")
            return
        
        if messagebox.askyesno("Confirmar", "Limpar todos os comandos?"):
            self.bot.commands.clear()
            self.refresh_command_list()
    
    def move_command_up(self):
        """Move o(s) comando(s) selecionado(s) para cima na lista"""
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível mover comandos enquanto o macro está rodando!\nPause o macro primeiro.")
            return
        
        selection = self.cmd_listbox.curselection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um ou mais comandos para mover!")
            return
        
        # Verifica se o primeiro comando está no topo
        if selection[0] == 0:
            messagebox.showwarning("Aviso", "Não é possível mover para cima!")
            return
        
        # Move todos os comandos selecionados uma posição para cima
        for idx in sorted(selection):
            self.bot.commands[idx-1], self.bot.commands[idx] = self.bot.commands[idx], self.bot.commands[idx-1]
        
        self.refresh_command_list()
        
        # Seleciona os comandos nas novas posições
        new_selection = tuple(i - 1 for i in selection)
        for idx in new_selection:
            self.cmd_listbox.selection_set(idx)
    
    def move_command_down(self):
        """Move o(s) comando(s) selecionado(s) para baixo na lista"""
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível mover comandos enquanto o macro está rodando!\nPause o macro primeiro.")
            return
        
        selection = self.cmd_listbox.curselection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um ou mais comandos para mover!")
            return
        
        # Verifica se o último comando está no final
        if selection[-1] >= len(self.bot.commands) - 1:
            messagebox.showwarning("Aviso", "Não é possível mover para baixo!")
            return
        
        # Move todos os comandos selecionados uma posição para baixo (em ordem reversa)
        for idx in sorted(selection, reverse=True):
            self.bot.commands[idx], self.bot.commands[idx+1] = self.bot.commands[idx+1], self.bot.commands[idx]
        
        self.refresh_command_list()
        
        # Seleciona os comandos nas novas posições
        new_selection = tuple(i + 1 for i in selection)
        for idx in new_selection:
            self.cmd_listbox.selection_set(idx)
    
    def copy_command(self):
        """Copia o(s) comando(s) selecionado(s) para a área de transferência interna"""
        selection = self.cmd_listbox.curselection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um ou mais comandos para copiar!")
            return
        
        # Faz uma cópia profunda dos comandos selecionados
        import copy
        if len(selection) == 1:
            # Se for um comando, armazena como um único comando
            self.clipboard_command = copy.deepcopy(self.bot.commands[selection[0]])
            self.clipboard_is_multiple = False
        else:
            # Se for múltiplos, armazena como uma lista
            self.clipboard_command = [copy.deepcopy(self.bot.commands[idx]) for idx in selection]
            self.clipboard_is_multiple = True
    
    def paste_command(self):
        """Cola o(s) comando(s) copiado(s) na lista"""
        if self.clipboard_command is None:
            messagebox.showwarning("Aviso", "Nenhum comando copiado! Use o botão 'Copiar' primeiro.")
            return
        
        # Cria uma cópia dos comandos copiados
        import copy
        
        # Obtém a posição selecionada, se houver
        selection = self.cmd_listbox.curselection()
        insert_idx = selection[0] + 1 if selection else len(self.bot.commands)
        
        if self.clipboard_is_multiple:
            # Cola múltiplos comandos
            for i, cmd in enumerate(self.clipboard_command):
                new_command = copy.deepcopy(cmd)
                self.bot.commands.insert(insert_idx + i, new_command)
        else:
            # Cola um único comando
            new_command = copy.deepcopy(self.clipboard_command)
            self.bot.commands.insert(insert_idx, new_command)
        
        self.refresh_command_list()
        
    def copy_command_shortcut(self, event):
        """Atalho Ctrl+C para copiar"""
        self.copy_command()
        
    def paste_command_shortcut(self, event):
        """Atalho Ctrl+V para colar"""
        self.paste_command()
        
    def show_context_menu(self, event):
        """Menu de contexto (botão direito)"""
        selection = self.cmd_listbox.curselection()
        
        # Cria menu
        menu = tk.Menu(self.root, tearoff=0)
        
        if selection:
            idx = selection[0]
            menu.add_command(label="📝 Editar", command=self.edit_command_from_menu)
            menu.add_command(label="⬆️ Mover Acima", command=self.move_command_up)
            menu.add_command(label="⬇️ Mover Abaixo", command=self.move_command_down)
            menu.add_separator()
            menu.add_command(label="📋 Copiar", command=self.copy_command)
            menu.add_command(label="📌 Colar", command=self.paste_command)
            menu.add_separator()
            menu.add_command(label="🗑️ Excluir", command=lambda: self.delete_command(None))
        else:
            menu.add_command(label="📌 Colar", command=self.paste_command, state="normal" if self.clipboard_command else "disabled")
        
        # Exibe menu na posição do mouse
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def edit_command_from_menu(self):
        """Editar comando a partir do menu de contexto"""
        selection = self.cmd_listbox.curselection()
        if selection:
            self.edit_command(None)
        
    def create_log_panel(self, parent):
        log_card = ttk.Frame(parent, style="Card.TFrame")
        log_card.pack(fill="both", expand=True)
        
        ttk.Label(log_card, text="📊 LOG", style="Title.TLabel").pack(pady=10)
        
        log_frame = tk.Frame(log_card, bg=self.colors["bg_light"])
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        scrollbar = tk.Scrollbar(log_frame, bg=self.colors["accent"])
        scrollbar.pack(side="right", fill="y")
        
        self.log_text = tk.Text(log_frame, yscrollcommand=scrollbar.set,
                               bg="#0a0a0a", fg="#00ff00", font=("Consolas", 9),
                               relief="flat", highlightthickness=0, state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Tags de cores
        self.log_text.tag_config("INFO", foreground="#00ff00")
        self.log_text.tag_config("SUCCESS", foreground="#06ffa5")
        self.log_text.tag_config("WARN", foreground="#ffd93d")
        self.log_text.tag_config("ERROR", foreground="#e94560")
        
        # Botão limpar log
        tk.Button(log_card, text="🗑 Limpar Log", command=self.clear_log,
                 bg="#5a5a5a", fg=self.colors["text"], font=("Arial", 9),
                 padx=15, pady=5, relief="flat", cursor="hand2").pack(pady=5)
        
    def add_log(self, message, level="INFO"):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n", level)
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        
    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")
    
    def add_command_dialog(self):
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível adicionar comandos enquanto o macro está rodando!\nPause o macro primeiro.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Adicionar Comando")
        dialog.geometry("600x550")  # Tamanho fixo
        dialog.configure(bg=self.colors["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Posiciona a janela de diálogo no mesmo lugar da interface principal
        self.position_dialog_window(dialog)
        
        tk.Label(dialog, text="Tipo de Comando:", bg=self.colors["bg"],
                fg=self.colors["text"], font=("Arial", 10, "bold")).pack(pady=10)
        
        cmd_display_list = list(self.cmd_display.keys())
        type_var = tk.StringVar(value=cmd_display_list[0])
        combo = ttk.Combobox(dialog, textvariable=type_var, values=cmd_display_list, state="readonly", width=35)
        combo.pack()
        
        tk.Label(dialog, text="Valor / Coordenadas:", bg=self.colors["bg"],
                fg=self.colors["text"]).pack(pady=(10, 0))
        
        # Frame para valor (pode ser Entry, Combobox ou seletor)
        value_frame = tk.Frame(dialog, bg=self.colors["bg"])
        value_frame.pack(pady=5)
        
        # Entry padrão
        value_entry = tk.Entry(value_frame, bg="#0f3460", fg=self.colors["text"],
                              relief="flat", width=40)
        value_entry.pack()
        
        # Combobox para teclas
        value_combo = ttk.Combobox(value_frame, values=self.available_keys, state="readonly", width=37)
        
        # Frame para teclas adicionais (modificadores)
        key_modifiers_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        tk.Label(key_modifiers_frame, text="Teclas adicionais:", bg=self.colors["bg"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack()
        
        mod_frame = tk.Frame(key_modifiers_frame, bg=self.colors["bg"])
        mod_frame.pack()
        
        ctrl_var = tk.BooleanVar()
        alt_var = tk.BooleanVar()
        shift_var = tk.BooleanVar()
        
        tk.Checkbutton(mod_frame, text="Ctrl", variable=ctrl_var, bg=self.colors["bg"],
                      fg=self.colors["text"], selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Checkbutton(mod_frame, text="Alt", variable=alt_var, bg=self.colors["bg"],
                      fg=self.colors["text"], selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Checkbutton(mod_frame, text="Shift", variable=shift_var, bg=self.colors["bg"],
                      fg=self.colors["text"], selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        # Opção de ação da tecla
        key_action_frame = tk.Frame(key_modifiers_frame, bg=self.colors["bg"])
        key_action_frame.pack(pady=5)
        
        tk.Label(key_action_frame, text="Ação da tecla:", bg=self.colors["bg"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=5)
        
        key_action_var = tk.StringVar(value="normal")
        
        tk.Radiobutton(key_action_frame, text="Normal", variable=key_action_var, value="normal",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(key_action_frame, text="Pressionar", variable=key_action_var, value="down",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(key_action_frame, text="Liberar", variable=key_action_var, value="up",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        # Opção para segurar tecla
        hold_frame = tk.Frame(key_modifiers_frame, bg=self.colors["bg"])
        hold_frame.pack(pady=5)
        
        hold_key_var = tk.BooleanVar(value=False)
        tk.Checkbutton(hold_frame, text="Segurar tecla por", variable=hold_key_var,
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        hold_time_entry = tk.Entry(hold_frame, bg="#0f3460", fg=self.colors["text"],
                                  relief="flat", width=8)
        hold_time_entry.insert(0, "1.0")
        hold_time_entry.pack(side="left", padx=5)
        
        tk.Label(hold_frame, text="segundos", bg=self.colors["bg"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=2)
        
        # Seletor de imagens
        image_selector_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        
        # Combobox com imagens existentes
        image_combo = ttk.Combobox(image_selector_frame, values=[], state="readonly", width=28)
        image_combo.pack(side="left", padx=5)
        
        def refresh_images():
            folder = self.bot.config.data["folder"]
            if os.path.exists(folder):
                images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
                image_combo['values'] = images
                if images:
                    image_combo.set(images[0])
        
        tk.Button(image_selector_frame, text="🔄", command=refresh_images,
                 bg=self.colors["accent"], fg=self.colors["text"],
                 relief="flat", cursor="hand2", width=2).pack(side="left", padx=2)
        
        # Botão para escolher imagem do computador
        def select_image_file():
            filepath = filedialog.askopenfilename(
                title="Selecionar Imagem",
                filetypes=[
                    ("Imagens", "*.png *.jpg *.jpeg *.bmp"),
                    ("PNG", "*.png"),
                    ("JPEG", "*.jpg *.jpeg"),
                    ("Todos os arquivos", "*.*")
                ]
            )
            
            if filepath:
                try:
                    # Copia imagem para pasta targets
                    import shutil
                    folder = self.bot.config.data["folder"]
                    if not os.path.exists(folder):
                        os.makedirs(folder)
                    
                    filename = os.path.basename(filepath)
                    # Adiciona timestamp se já existir
                    if os.path.exists(os.path.join(folder, filename)):
                        name, ext = os.path.splitext(filename)
                        filename = f"{name}_{int(time.time())}{ext}"
                    
                    dest_path = os.path.join(folder, filename)
                    shutil.copy2(filepath, dest_path)
                    
                    refresh_images()
                    image_combo.set(filename)
                    messagebox.showinfo("Sucesso", f"Imagem importada: {filename}")
                    
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao importar imagem: {e}")
        
        tk.Button(image_selector_frame, text="📁", command=select_image_file,
                 bg=self.colors["success"], fg="#000",
                 relief="flat", cursor="hand2", width=2,
                 font=("Arial", 10, "bold")).pack(side="left", padx=2)
        
        tk.Label(image_selector_frame, text="Escolher imagem",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        # Seletor de pasta (para click_folder)
        folder_selector_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        
        folder_path_var = tk.StringVar(value="")
        folder_entry = tk.Entry(folder_selector_frame, textvariable=folder_path_var,
                               bg="#0f3460", fg=self.colors["text"], relief="flat", width=28)
        folder_entry.pack(side="left", padx=5)
        
        def select_folder_path():
            folder = filedialog.askdirectory(title="Selecionar Pasta com Imagens")
            if folder:
                folder_path_var.set(folder)
        
        tk.Button(folder_selector_frame, text="📁", command=select_folder_path,
                 bg=self.colors["success"], fg="#000",
                 relief="flat", cursor="hand2", width=2,
                 font=("Arial", 10, "bold")).pack(side="left", padx=2)
        
        tk.Label(folder_selector_frame, text="Pasta com imagens",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        # Frame para SE/SENAO
        se_senao_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        
        tk.Label(se_senao_frame, text="Tipo de Condição:", bg=self.colors["bg"],
                fg=self.colors["text"], font=("Arial", 9)).pack(anchor="w", padx=10, pady=(5, 2))
        
        condition_type_var = tk.StringVar(value="image")
        
        image_radio = tk.Radiobutton(se_senao_frame, text="Verificar Imagem", variable=condition_type_var,
                      value="image", bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"])
        image_radio.pack(anchor="w", padx=20)
        
        multi_image_radio = tk.Radiobutton(se_senao_frame, text="Verificar Múltiplas Imagens (qualquer uma)", variable=condition_type_var,
                      value="multi_image", bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"])
        multi_image_radio.pack(anchor="w", padx=20)
        
        text_radio = tk.Radiobutton(se_senao_frame, text="Verificar Texto (OCR)", variable=condition_type_var,
                      value="text", bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"])
        text_radio.pack(anchor="w", padx=20)
        
        # Frame para seletor de imagem única
        se_image_frame = tk.Frame(se_senao_frame, bg=self.colors["bg"])
        se_image_frame.pack(anchor="w", padx=20, pady=5, fill="x")
        
        se_image_combo = ttk.Combobox(se_image_frame, values=[], state="readonly", width=28)
        se_image_combo.pack(side="left", padx=2)
        
        def refresh_se_images():
            folder = self.bot.config.data["folder"]
            if os.path.exists(folder):
                images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
                se_image_combo['values'] = images
                if images:
                    se_image_combo.set(images[0])
        
        tk.Button(se_image_frame, text="🔄", command=refresh_se_images,
                 bg=self.colors["accent"], fg=self.colors["text"],
                 relief="flat", cursor="hand2", width=2).pack(side="left", padx=2)
        
        def select_se_image_file():
            filepath = filedialog.askopenfilename(
                title="Selecionar Imagem",
                filetypes=[
                    ("Imagens", "*.png *.jpg *.jpeg *.bmp"),
                    ("PNG", "*.png"),
                    ("JPEG", "*.jpg *.jpeg"),
                    ("Todos os arquivos", "*.*")
                ]
            )
            
            if filepath:
                try:
                    import shutil
                    folder = self.bot.config.data["folder"]
                    if not os.path.exists(folder):
                        os.makedirs(folder)
                    
                    filename = os.path.basename(filepath)
                    if os.path.exists(os.path.join(folder, filename)):
                        name, ext = os.path.splitext(filename)
                        filename = f"{name}_{int(time.time())}{ext}"
                    
                    dest_path = os.path.join(folder, filename)
                    shutil.copy2(filepath, dest_path)
                    
                    refresh_se_images()
                    se_image_combo.set(filename)
                    messagebox.showinfo("Sucesso", f"Imagem importada: {filename}")
                    
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao importar imagem: {e}")
        
        tk.Button(se_image_frame, text="📁", command=select_se_image_file,
                 bg=self.colors["success"], fg="#000",
                 relief="flat", cursor="hand2", width=2,
                 font=("Arial", 10, "bold")).pack(side="left", padx=2)
        
        tk.Label(se_image_frame, text="Carregar",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        # Frame para múltiplas imagens
        se_multi_image_frame = tk.Frame(se_senao_frame, bg=self.colors["bg"])
        se_multi_image_frame.pack(anchor="w", padx=20, pady=5, fill="both")
        
        tk.Label(se_multi_image_frame, text="Pasta com imagens:",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 8)).pack(anchor="w", pady=2)
        
        # Frame com entry e botão
        multi_folder_frame = tk.Frame(se_multi_image_frame, bg=self.colors["bg"])
        multi_folder_frame.pack(fill="x", pady=2)
        
        se_multi_folder_var = tk.StringVar(value="")
        se_multi_folder_entry = tk.Entry(multi_folder_frame, textvariable=se_multi_folder_var,
                                        bg="#0f3460", fg=self.colors["text"], 
                                        relief="flat", width=35)
        se_multi_folder_entry.pack(side="left", padx=2)
        
        def select_multi_folder():
            folder = filedialog.askdirectory(title="Selecionar Pasta com Imagens")
            if folder:
                se_multi_folder_var.set(folder)
                # Conta e mostra quantas imagens
                try:
                    images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
                    se_multi_info_label.config(text=f"✓ {len(images)} imagens encontradas")
                except:
                    se_multi_info_label.config(text="✗ Erro ao ler pasta")
        
        tk.Button(multi_folder_frame, text="📁 Selecionar Pasta", 
                 command=select_multi_folder,
                 bg=self.colors["success"], fg="#000",
                 relief="flat", cursor="hand2",
                 font=("Arial", 9, "bold"), padx=10, pady=3).pack(side="left", padx=2)
        
        se_multi_info_label = tk.Label(se_multi_image_frame, text="Nenhuma pasta selecionada",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7))
        se_multi_info_label.pack(anchor="w", pady=2)
        
        # Frame para entrada de texto
        se_text_frame = tk.Frame(se_senao_frame, bg=self.colors["bg"])
        se_text_frame.pack(anchor="w", padx=20, pady=5, fill="x")
        
        se_value_entry = tk.Entry(se_text_frame, bg="#0f3460", fg=self.colors["text"],
                                 relief="flat", width=40)
        se_value_entry.pack(side="left", padx=2)
        
        tk.Label(se_text_frame, text="Digite o texto ou selecione imagem acima",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        # Frame para comando STOP
        stop_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        
        tk.Label(stop_frame, text="Tipo de Validação:", bg=self.colors["bg"],
                fg=self.colors["text"], font=("Arial", 9)).pack(anchor="w", padx=10, pady=(5, 2))
        
        stop_type_var = tk.StringVar(value="image")
        
        stop_image_radio = tk.Radiobutton(stop_frame, text="Parar quando encontrar Imagem", 
                      variable=stop_type_var, value="image",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"])
        stop_image_radio.pack(anchor="w", padx=20)
        
        stop_text_radio = tk.Radiobutton(stop_frame, text="Parar quando encontrar Texto (OCR)", 
                      variable=stop_type_var, value="text",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"])
        stop_text_radio.pack(anchor="w", padx=20)
        
        # Frame para seletor de imagem do stop
        stop_image_frame = tk.Frame(stop_frame, bg=self.colors["bg"])
        stop_image_frame.pack(anchor="w", padx=20, pady=5, fill="x")
        
        stop_image_combo = ttk.Combobox(stop_image_frame, values=[], state="readonly", width=28)
        stop_image_combo.pack(side="left", padx=2)
        
        def refresh_stop_images():
            folder = self.bot.config.data["folder"]
            if os.path.exists(folder):
                images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
                stop_image_combo['values'] = images
                if images:
                    stop_image_combo.set(images[0])
        
        tk.Button(stop_image_frame, text="🔄", command=refresh_stop_images,
                 bg=self.colors["accent"], fg=self.colors["text"],
                 relief="flat", cursor="hand2", width=2).pack(side="left", padx=2)
        
        # Frame para entrada de texto do stop
        stop_text_frame = tk.Frame(stop_frame, bg=self.colors["bg"])
        stop_text_frame.pack(anchor="w", padx=20, pady=5, fill="x")
        
        stop_text_entry = tk.Entry(stop_text_frame, bg="#0f3460", fg=self.colors["text"],
                                  relief="flat", width=40)
        stop_text_entry.pack(side="left", padx=2)
        
        tk.Label(stop_text_frame, text="Digite o texto ou selecione imagem acima",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        def update_stop_inputs(*args):
            """Mostra/esconde inputs baseado no tipo de validação"""
            val_type = stop_type_var.get()
            if val_type == "image":
                stop_image_frame.pack(anchor="w", padx=20, pady=5, fill="x")
                stop_text_frame.pack_forget()
            else:  # text
                stop_text_frame.pack(anchor="w", padx=20, pady=5, fill="x")
                stop_image_frame.pack_forget()
        
        stop_type_var.trace("w", update_stop_inputs)
        refresh_stop_images()
        update_stop_inputs()
        
        def update_se_inputs(*args):
            """Mostra/esconde inputs baseado no tipo de condição"""
            cond_type = condition_type_var.get()
            if cond_type == "image":
                se_image_frame.pack(anchor="w", padx=20, pady=5, fill="x")
                se_multi_image_frame.pack_forget()
                se_text_frame.pack_forget()
            elif cond_type == "multi_image":
                se_image_frame.pack_forget()
                se_multi_image_frame.pack(anchor="w", padx=20, pady=5, fill="both")
                se_text_frame.pack_forget()
            else:  # text
                se_text_frame.pack(anchor="w", padx=20, pady=5, fill="x")
                se_image_frame.pack_forget()
                se_multi_image_frame.pack_forget()
        
        condition_type_var.trace("w", update_se_inputs)
        
        # Inicializa carregando imagens
        refresh_se_images()
        update_se_inputs()
        
        # Frame para arrastar (drag)
        drag_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        
        # Coordenadas de início
        start_frame = tk.Frame(drag_frame, bg=self.colors["bg"])
        start_frame.pack(pady=2)
        
        tk.Label(start_frame, text="Início:", bg=self.colors["bg"], fg=self.colors["text"],
                font=("Arial", 9)).pack(side="left", padx=5)
        
        start_coord_entry = tk.Entry(start_frame, bg="#0f3460", fg=self.colors["text"],
                                    relief="flat", width=15)
        start_coord_entry.pack(side="left", padx=5)
        start_coord_entry.insert(0, "0,0")
        
        # Label para mostrar posição atual (início)
        start_pos_label = tk.Label(start_frame, text="(0, 0)", bg=self.colors["bg"],
                                  fg=self.colors["warning"], font=("Arial", 9))
        start_pos_label.pack(side="left", padx=5)
        
        # Estado de captura para coordenada de início
        capturing_start = {"active": False}
        
        def update_start_mouse_pos():
            if capturing_start["active"]:
                x, y = pyautogui.position()
                start_pos_label.config(text=f"({x}, {y})")
                dialog.after(50, update_start_mouse_pos)
        
        def toggle_start_capture():
            if not capturing_start["active"]:
                capturing_start["active"] = True
                start_capture_btn.config(text="⏹ Parar (Alt)", bg=self.colors["primary"])
                update_start_mouse_pos()
                
                def on_alt_press_start(e):
                    if capturing_start["active"]:
                        x, y = pyautogui.position()
                        start_coord_entry.delete(0, tk.END)
                        start_coord_entry.insert(0, f"{x},{y}")
                        capturing_start["active"] = False
                        start_capture_btn.config(text="📍 Capturar", bg=self.colors["success"])
                        start_pos_label.config(text="(0, 0)")
                        dialog.unbind("<Alt_L>")
                        dialog.unbind("<Alt_R>")
                
                dialog.bind("<Alt_L>", on_alt_press_start)
                dialog.bind("<Alt_R>", on_alt_press_start)
            else:
                capturing_start["active"] = False
                start_capture_btn.config(text="📍 Capturar", bg=self.colors["success"])
                start_pos_label.config(text="(0, 0)")
        
        start_capture_btn = tk.Button(start_frame, text="📍 Capturar",
                                     command=toggle_start_capture,
                                     bg=self.colors["success"], fg="#000", relief="flat",
                                     cursor="hand2", font=("Arial", 8))
        start_capture_btn.pack(side="left", padx=2)
        
        # Coordenadas de fim
        end_frame = tk.Frame(drag_frame, bg=self.colors["bg"])
        end_frame.pack(pady=2)
        
        tk.Label(end_frame, text="Fim:", bg=self.colors["bg"], fg=self.colors["text"],
                font=("Arial", 9)).pack(side="left", padx=5)
        
        end_coord_entry = tk.Entry(end_frame, bg="#0f3460", fg=self.colors["text"],
                                  relief="flat", width=15)
        end_coord_entry.pack(side="left", padx=5)
        end_coord_entry.insert(0, "100,100")
        
        # Label para mostrar posição atual (fim)
        end_pos_label = tk.Label(end_frame, text="(0, 0)", bg=self.colors["bg"],
                                fg=self.colors["warning"], font=("Arial", 9))
        end_pos_label.pack(side="left", padx=5)
        
        # Estado de captura para coordenada de fim
        capturing_end = {"active": False}
        
        def update_end_mouse_pos():
            if capturing_end["active"]:
                x, y = pyautogui.position()
                end_pos_label.config(text=f"({x}, {y})")
                dialog.after(50, update_end_mouse_pos)
        
        def toggle_end_capture():
            if not capturing_end["active"]:
                capturing_end["active"] = True
                end_capture_btn.config(text="⏹ Parar (Alt)", bg=self.colors["primary"])
                update_end_mouse_pos()
                
                def on_alt_press_end(e):
                    if capturing_end["active"]:
                        x, y = pyautogui.position()
                        end_coord_entry.delete(0, tk.END)
                        end_coord_entry.insert(0, f"{x},{y}")
                        capturing_end["active"] = False
                        end_capture_btn.config(text="📍 Capturar", bg=self.colors["success"])
                        end_pos_label.config(text="(0, 0)")
                        dialog.unbind("<Alt_L>")
                        dialog.unbind("<Alt_R>")
                
                dialog.bind("<Alt_L>", on_alt_press_end)
                dialog.bind("<Alt_R>", on_alt_press_end)
            else:
                capturing_end["active"] = False
                end_capture_btn.config(text="📍 Capturar", bg=self.colors["success"])
                end_pos_label.config(text="(0, 0)")
        
        end_capture_btn = tk.Button(end_frame, text="📍 Capturar",
                                   command=toggle_end_capture,
                                   bg=self.colors["success"], fg="#000", relief="flat",
                                   cursor="hand2", font=("Arial", 8))
        end_capture_btn.pack(side="left", padx=2)
        
        # Opções do mouse
        mouse_frame = tk.Frame(drag_frame, bg=self.colors["bg"])
        mouse_frame.pack(pady=5)
        
        tk.Label(mouse_frame, text="Botão:", bg=self.colors["bg"], fg=self.colors["text"],
                font=("Arial", 9)).pack(side="left", padx=5)
        
        drag_button_var = tk.StringVar(value="left")
        tk.Radiobutton(mouse_frame, text="Esquerdo", variable=drag_button_var, value="left",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(mouse_frame, text="Direito", variable=drag_button_var, value="right",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        # Frame para coordenadas com captura
        coord_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        coord_entry = tk.Entry(coord_frame, bg="#0f3460", fg=self.colors["text"],
                              relief="flat", width=25)
        coord_entry.pack(side="left", padx=5)
        coord_entry.insert(0, "0,0")
        
        current_pos_label = tk.Label(coord_frame, text="(0, 0)", bg=self.colors["bg"],
                                     fg=self.colors["warning"], font=("Arial", 9))
        current_pos_label.pack(side="left", padx=5)
        
        capturing_coords = {"active": False}
        
        def update_mouse_pos():
            if capturing_coords["active"]:
                x, y = pyautogui.position()
                current_pos_label.config(text=f"({x}, {y})")
                dialog.after(50, update_mouse_pos)
        
        def toggle_coord_capture():
            if not capturing_coords["active"]:
                capturing_coords["active"] = True
                capture_btn.config(text="⏹ Parar (Alt)", bg=self.colors["primary"])
                update_mouse_pos()
                
                def on_alt_press(e):
                    if capturing_coords["active"]:
                        x, y = pyautogui.position()
                        coord_entry.delete(0, tk.END)
                        coord_entry.insert(0, f"{x},{y}")
                        capturing_coords["active"] = False
                        capture_btn.config(text="📍 Capturar Posição", bg=self.colors["success"])
                        dialog.unbind("<Alt_L>")
                        dialog.unbind("<Alt_R>")
                
                dialog.bind("<Alt_L>", on_alt_press)
                dialog.bind("<Alt_R>", on_alt_press)
            else:
                capturing_coords["active"] = False
                capture_btn.config(text="📍 Capturar Posição", bg=self.colors["success"])
        
        capture_btn = tk.Button(coord_frame, text="📍 Capturar Posição",
                               command=toggle_coord_capture,
                               bg=self.colors["success"], fg="#000",
                               relief="flat", cursor="hand2", font=("Arial", 8))
        capture_btn.pack(side="left", padx=5)
        
        tk.Label(coord_frame, text="Mova o mouse e pressione Alt",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=5)
        
        def on_type_change(*args):
            cmd_type = self.cmd_display[type_var.get()]
            
            # Esconde tudo primeiro
            value_entry.pack_forget()
            value_combo.pack_forget()
            key_modifiers_frame.pack_forget()
            image_selector_frame.pack_forget()
            folder_selector_frame.pack_forget()
            drag_frame.pack_forget()
            coord_frame.pack_forget()
            se_senao_frame.pack_forget()
            stop_frame.pack_forget()
            
            # Não ajusta mais o tamanho, mantém fixo em 500px
            if cmd_type == "key":
                value_combo.pack()
                value_combo.set("enter")
                key_modifiers_frame.pack(pady=5)
            elif cmd_type in ["click_image"]:
                refresh_images()
                image_selector_frame.pack()
            elif cmd_type == "click_folder":
                folder_selector_frame.pack()
            elif cmd_type == "se":
                se_senao_frame.pack(anchor="w", padx=0, pady=5)
            elif cmd_type == "stop":
                stop_frame.pack(anchor="w", padx=0, pady=5)
            elif cmd_type in ["senao", "fim"]:
                # SENAO e FIM não precisam de valor
                pass
            elif cmd_type == "drag":
                drag_frame.pack()
            elif cmd_type in ["move_mouse", "click_pos"]:
                coord_frame.pack()
            else:
                value_entry.pack()
                value_entry.delete(0, tk.END)
        
        type_var.trace("w", on_type_change)
        
        tk.Label(dialog, text="Delay após comando (s):", bg=self.colors["bg"],
                fg=self.colors["text"]).pack(pady=(10, 0))
        delay_entry = tk.Entry(dialog, bg="#0f3460", fg=self.colors["text"],
                              relief="flat", width=10)
        delay_entry.insert(0, "0")
        delay_entry.pack(pady=5)
        
        # Frame de opções extras (visível apenas para certos comandos)
        extras_frame = tk.Frame(dialog, bg=self.colors["bg"])
        
        # Opções de clique variável
        tk.Label(extras_frame, text="Opções extras:", bg=self.colors["bg"],
                fg=self.colors["text"], font=("Arial", 9, "bold")).pack(pady=(10, 0))
        
        click_options_frame = tk.Frame(extras_frame, bg=self.colors["bg_light"], relief="groove", borderwidth=2)
        click_options_frame.pack(pady=5, padx=20, fill="x")
        
        tk.Label(click_options_frame, text="🎯 Posição de Clique:", bg=self.colors["bg_light"],
                fg=self.colors["text"], font=("Arial", 9, "bold")).pack(pady=5)
        
        click_mode_var = tk.StringVar(value="fixed")
        
        fixed_radio = tk.Radiobutton(click_options_frame, text="Fixa (sempre no centro)", 
                                    variable=click_mode_var, value="fixed",
                                    bg=self.colors["bg_light"], fg=self.colors["text"],
                                    selectcolor=self.colors["accent"])
        fixed_radio.pack(anchor="w", padx=10)
        
        variable_radio = tk.Radiobutton(click_options_frame, text="Variável (aleatório ao redor)", 
                                       variable=click_mode_var, value="variable",
                                       bg=self.colors["bg_light"], fg=self.colors["text"],
                                       selectcolor=self.colors["accent"])
        variable_radio.pack(anchor="w", padx=10)
        
        # Frame para raio variável
        radius_frame = tk.Frame(click_options_frame, bg=self.colors["bg_light"])
        radius_frame.pack(pady=5, padx=20, fill="x")
        
        tk.Label(radius_frame, text="Raio de variação (pixels):", bg=self.colors["bg_light"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=5)
        
        radius_var = tk.IntVar(value=5)
        radius_spinbox = tk.Spinbox(radius_frame, from_=1, to=50, textvariable=radius_var,
                                   bg="#0f3460", fg=self.colors["text"], width=8,
                                   relief="flat", state="disabled")
        radius_spinbox.pack(side="left", padx=5)
        
        tk.Label(radius_frame, text="(quanto maior, mais disperso o clique)", 
                bg=self.colors["bg_light"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=5)
        
        def toggle_radius_spinbox(*args):
            if click_mode_var.get() == "variable":
                radius_spinbox.config(state="normal")
            else:
                radius_spinbox.config(state="disabled")
        
        click_mode_var.trace("w", toggle_radius_spinbox)
        
        # Opção de botão do mouse
        mouse_button_frame = tk.Frame(click_options_frame, bg=self.colors["bg_light"])
        mouse_button_frame.pack(pady=5, padx=20, fill="x")
        
        tk.Label(mouse_button_frame, text="Botão do mouse:", bg=self.colors["bg_light"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=5)
        
        mouse_button_var = tk.StringVar(value="left")
        
        tk.Radiobutton(mouse_button_frame, text="Esquerdo", variable=mouse_button_var, value="left",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(mouse_button_frame, text="Direito", variable=mouse_button_var, value="right",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(mouse_button_frame, text="Meio", variable=mouse_button_var, value="middle",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        # Opção de ação do clique
        click_action_frame = tk.Frame(click_options_frame, bg=self.colors["bg_light"])
        click_action_frame.pack(pady=5, padx=20, fill="x")
        
        tk.Label(click_action_frame, text="Ação do clique:", bg=self.colors["bg_light"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=5)
        
        click_action_var = tk.StringVar(value="normal")
        
        tk.Radiobutton(click_action_frame, text="Normal", variable=click_action_var, value="normal",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(click_action_frame, text="Pressionar", variable=click_action_var, value="down",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(click_action_frame, text="Liberar", variable=click_action_var, value="up",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        # Tempo de segurar botão
        hold_frame = tk.Frame(click_options_frame, bg=self.colors["bg_light"])
        hold_frame.pack(pady=5, padx=20, fill="x")
        
        tk.Label(hold_frame, text="Segurar botão (segundos):", bg=self.colors["bg_light"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=5)
        
        hold_time_var = tk.DoubleVar(value=0)
        hold_spinbox = tk.Spinbox(hold_frame, from_=0, to=10, increment=0.1, textvariable=hold_time_var,
                                 bg="#0f3460", fg=self.colors["text"], width=8, relief="flat")
        hold_spinbox.pack(side="left", padx=5)
        
        tk.Label(hold_frame, text="(0 = clique normal)", 
                bg=self.colors["bg_light"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=5)
        
        # Mostrar/esconder opções baseado no tipo
        def update_extras_visibility(*args):
            cmd_type = self.cmd_display[type_var.get()]
            
            if cmd_type in ["click_image", "click_folder", "click", "click_pos"]:
                extras_frame.pack(fill="x", pady=5)
            else:
                extras_frame.pack_forget()
        
        type_var.trace("w", update_extras_visibility)
        
        # Outras opções (JSON) - removido
        
        def add():
            try:
                display_type = type_var.get()
                cmd_type = self.cmd_display[display_type]
                cmd_value = ""
                
                # Pega valor do campo apropriado
                if cmd_type == "key":
                    base_key = value_combo.get()
                    modifiers = []
                    if ctrl_var.get():
                        modifiers.append("ctrl")
                    if alt_var.get():
                        modifiers.append("alt")
                    if shift_var.get():
                        modifiers.append("shift")
                    
                    if modifiers:
                        cmd_value = "+".join(modifiers) + "+" + base_key
                    else:
                        cmd_value = base_key
                elif cmd_type == "click_image":
                    cmd_value = image_combo.get()
                    if not cmd_value:
                        messagebox.showwarning("Aviso", "Selecione uma imagem!")
                        return
                elif cmd_type == "click_folder":
                    cmd_value = folder_path_var.get()
                    if not cmd_value:
                        messagebox.showwarning("Aviso", "Selecione uma pasta!")
                        return
                elif cmd_type == "se":
                    condition_type = condition_type_var.get()
                    if condition_type == "image":
                        cmd_value = se_image_combo.get()
                        if not cmd_value:
                            messagebox.showwarning("Aviso", "Selecione uma imagem para a condição SE!")
                            return
                    elif condition_type == "multi_image":
                        cmd_value = se_multi_folder_var.get()
                        if not cmd_value:
                            messagebox.showwarning("Aviso", "Selecione uma pasta com imagens!")
                            return
                        if not os.path.exists(cmd_value):
                            messagebox.showwarning("Aviso", "A pasta selecionada não existe!")
                            return
                    else:  # text
                        cmd_value = se_value_entry.get().strip()
                        if not cmd_value:
                            messagebox.showwarning("Aviso", "Digite o texto para a condição SE!")
                            return
                elif cmd_type == "senao":
                    # SENAO não precisa de valor
                    cmd_value = ""
                elif cmd_type == "fim":
                    # FIM não precisa de valor
                    cmd_value = ""
                elif cmd_type == "stop":
                    val_type = stop_type_var.get()
                    if val_type == "image":
                        cmd_value = stop_image_combo.get()
                        if not cmd_value:
                            messagebox.showwarning("Aviso", "Selecione uma imagem para validação!")
                            return
                    else:  # text
                        cmd_value = stop_text_entry.get().strip()
                        if not cmd_value:
                            messagebox.showwarning("Aviso", "Digite o texto para validação!")
                            return
                elif cmd_type == "drag":
                    start_coords = start_coord_entry.get().strip()
                    end_coords = end_coord_entry.get().strip()
                    if not start_coords or not end_coords:
                        messagebox.showwarning("Aviso", "Defina as coordenadas de início e fim!")
                        return
                    cmd_value = f"{start_coords},{end_coords}"
                elif cmd_type in ["move_mouse", "click_pos"]:
                    cmd_value = coord_entry.get().strip()
                else:
                    cmd_value = value_entry.get().strip()
                
                cmd_delay = float(delay_entry.get())
                
                cmd_options = {}
                
                # Adiciona opções específicas do comando
                if cmd_type == "key":
                    cmd_options["key_action"] = key_action_var.get()
                    if hold_key_var.get():
                        try:
                            hold_time = float(hold_time_entry.get())
                            cmd_options["hold_time"] = hold_time
                        except ValueError:
                            messagebox.showwarning("Aviso", "Tempo de duração inválido!")
                            return
                elif cmd_type == "se":
                    cmd_options["condition_type"] = condition_type_var.get()
                elif cmd_type == "stop":
                    cmd_options["stop_type"] = stop_type_var.get()
                elif cmd_type in ["click_image", "click_folder", "click", "click_pos"]:
                    cmd_options["click_mode"] = click_mode_var.get()
                    if click_mode_var.get() == "variable":
                        cmd_options["click_radius"] = radius_var.get()
                    cmd_options["button"] = mouse_button_var.get()
                    cmd_options["click_action"] = click_action_var.get()
                    cmd_options["hold_time"] = hold_time_var.get()
                elif cmd_type == "drag":
                    cmd_options["button"] = drag_button_var.get()
                
                command = {
                    "type": cmd_type,
                    "value": cmd_value,
                    "delay": cmd_delay,
                    "options": cmd_options
                }
                
                # Se for SE, adiciona SE, SENAO e FIM automaticamente
                if cmd_type == "se":
                    self.bot.commands.append(command)
                    
                    # Adiciona SENAO
                    senao_cmd = {
                        "type": "senao",
                        "value": "",
                        "delay": 0,
                        "options": {}
                    }
                    self.bot.commands.append(senao_cmd)
                    
                    # Adiciona FIM
                    fim_cmd = {
                        "type": "fim",
                        "value": "",
                        "delay": 0,
                        "options": {}
                    }
                    self.bot.commands.append(fim_cmd)
                else:
                    self.bot.commands.append(command)
                
                self.refresh_command_list()
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao adicionar comando: {e}")
        
        btn_frame = tk.Frame(dialog, bg=self.colors["bg"])
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="✓ Adicionar", command=add,
                 bg=self.colors["success"], fg="#000", font=("Arial", 10, "bold"),
                 padx=30, pady=8, relief="flat", cursor="hand2").pack(side="left", padx=5)
        
        tk.Button(btn_frame, text="✗ Cancelar", command=dialog.destroy,
                 padx=30, pady=8, relief="flat", cursor="hand2").pack(side="left", padx=5)
    
    def refresh_command_list(self):
        """Atualiza lista de comandos - otimizado"""
        # Limpa todos os itens
        for item in self.cmd_listbox.get_children():
            self.cmd_listbox.delete(item)
        
        # Dicionário reverso para exibição
        type_display = {
            "click_image": "🖱️ Clicar Imagem",
            "click_folder": "🖱️ Pasta",
            "click": "🖱️ Clicar",
            "key": "⌨️ Tecla",
            "type_text": "⌨️ Digitar",
            "move_mouse": "🖱️ Mover",
            "click_pos": "🖱️ Clicar Pos",
            "drag": "🖱️ Arrastar",
            "scroll": "🖱️ Scroll",
            "se": "🔀 SE",
            "senao": "🔚 SENAO",
            "fim": "🏁 FIM",
            "find_text": "🔍 Buscar Texto",
            "stop": "⏹ Parar",
            "delay": "⏱️ Delay",
            "comment": "💬 Comentário"
        }
        
        # Tags de cor por categoria
        click_types = {"click_image", "click_folder", "click", "click_pos", "move_mouse", "drag", "scroll"}
        key_types = {"key", "type_text"}
        control_types = {"se", "senao", "fim", "stop"}
        
        for i, cmd in enumerate(self.bot.commands):
            cmd_type = cmd['type']
            display_type = type_display.get(cmd_type, cmd_type)
            options = cmd.get('options', {})
            
            # Determinar tag de cor
            if cmd_type in click_types:
                tag = "click"
            elif cmd_type in key_types:
                key_action = options.get('key_action', 'normal')
                tag = "key_down" if key_action == 'down' else "key_up" if key_action == 'up' else "key"
            elif cmd_type in control_types:
                tag = "control"
            elif cmd_type == "delay":
                tag = "delay"
            else:
                tag = "other"
            
            # Preparar valor
            value = cmd['value']
            if cmd_type == "key":
                key_action = options.get('key_action', 'normal')
                if key_action == 'down':
                    value = f"↓ Pressionar: {value}"
                elif key_action == 'up':
                    value = f"↑ Liberar: {value}"
            
            # Preparar delay
            delay_value = cmd.get('delay', 0)
            delay_text = f"+{delay_value}s" if delay_value > 0 else "-"
            
            # Adicionar informações extras para SE
            if cmd_type == 'se':
                condition_type = options.get('condition_type', 'image')
                if condition_type == 'multi_image':
                    value = f"{value} [pasta]"
                elif condition_type != 'image':
                    value = f"{value} [{condition_type}]"
            
            # Inserir na tabela
            self.cmd_listbox.insert("", "end", values=(i+1, display_type, value, delay_text), tags=(tag,))
    
    def on_drag_start(self, event):
        """Inicia o drag and drop"""
        item = self.cmd_listbox.identify_row(event.y)
        if item:
            self.drag_item = item
            self.drag_start_index = self.cmd_listbox.index(item)
    
    def on_drag_motion(self, event):
        """Durante o movimento do drag"""
        if self.drag_item:
            # Identifica onde está o mouse
            target = self.cmd_listbox.identify_row(event.y)
            if target and target != self.drag_item:
                # Move visualmente
                self.cmd_listbox.selection_set(target)
    
    def on_drag_release(self, event):
        """Finaliza o drag and drop"""
        if self.drag_item:
            target = self.cmd_listbox.identify_row(event.y)
            if target and target != self.drag_item:
                target_index = self.cmd_listbox.index(target)
                
                # Move o comando na lista
                if 0 <= self.drag_start_index < len(self.bot.commands) and 0 <= target_index < len(self.bot.commands):
                    cmd = self.bot.commands.pop(self.drag_start_index)
                    self.bot.commands.insert(target_index, cmd)
                    self.refresh_command_list()
                    
                    # Seleciona o item movido
                    items = self.cmd_listbox.get_children()
                    if target_index < len(items):
                        self.cmd_listbox.selection_set(items[target_index])
        
        self.drag_item = None
        self.drag_start_index = None
    
    def edit_command_from_treeview(self, event):
        """Edita comando quando usando Treeview"""
        # Previne edição durante drag
        if self.drag_item:
            return
        
        selection = self.cmd_listbox.selection()
        if not selection:
            return
        
        idx = self.cmd_listbox.index(selection[0])
        self.edit_command_with_index(idx)
    
    def delete_command_from_treeview(self, event):
        """Deleta comando quando usando Treeview"""
        selection = self.cmd_listbox.selection()
        if not selection:
            return
        
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível deletar comandos enquanto o macro está rodando!")
            return
        
        idx = self.cmd_listbox.index(selection[0])
        if idx < len(self.bot.commands):
            del self.bot.commands[idx]
            self.refresh_command_list()
    
    def get_selected_line_index(self):
        """Obtém o índice da linha selecionada no Text widget"""
        try:
            # Pega a posição do cursor
            cursor_pos = self.cmd_listbox.index(tk.INSERT)
            line_num = int(cursor_pos.split('.')[0])
            # Linha do Text começa em 1, mas nosso índice começa em 0
            return line_num - 1
        except:
            return None
    
    def edit_command_from_text(self, event):
        """Edita comando quando usando Text widget"""
        idx = self.get_selected_line_index()
        if idx is None or idx >= len(self.bot.commands):
            return
        
        # Chama a função de edição original passando o índice
        self.edit_command_with_index(idx)
    
    def delete_command_from_text(self, event):
        """Deleta comando quando usando Text widget"""
        idx = self.get_selected_line_index()
        if idx is None or idx >= len(self.bot.commands):
            return
        
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível deletar comandos enquanto o macro está rodando!")
            return
        
        del self.bot.commands[idx]
        self.refresh_command_list()
    
    def edit_command(self, event):
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível editar comandos enquanto o macro está rodando!\nPause o macro primeiro.")
            return
        
        selection = self.cmd_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        self.edit_command_with_index(idx)
    
    def edit_command_with_index(self, idx):
        """Edita comando pelo índice"""
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível editar comandos enquanto o macro está rodando!\nPause o macro primeiro.")
            return
        
        if idx >= len(self.bot.commands):
            return
        
        cmd = self.bot.commands[idx]
        
        # Diálogo de edição
        dialog = tk.Toplevel(self.root)
        dialog.title("Editar Comando")
        dialog.geometry("600x550")  # Tamanho fixo
        dialog.configure(bg=self.colors["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Posiciona a janela de diálogo no mesmo lugar da interface principal
        self.position_dialog_window(dialog)
        
        tk.Label(dialog, text="Tipo de Comando:", bg=self.colors["bg"],
                fg=self.colors["text"], font=("Arial", 10, "bold")).pack(pady=10)
        
        # Encontra o display type atual
        current_display = None
        for display, cmd_type in self.cmd_display.items():
            if cmd_type == cmd['type']:
                current_display = display
                break
        
        cmd_display_list = list(self.cmd_display.keys())
        type_var = tk.StringVar(value=current_display or cmd_display_list[0])
        combo = ttk.Combobox(dialog, textvariable=type_var, values=cmd_display_list, state="readonly", width=35)
        combo.pack()
        
        tk.Label(dialog, text="Valor / Coordenadas:", bg=self.colors["bg"],
                fg=self.colors["text"]).pack(pady=(10, 0))
        
        # Frame para valor (pode ser Entry, Combobox ou seletor)
        value_frame = tk.Frame(dialog, bg=self.colors["bg"])
        value_frame.pack(pady=5)
        
        # Entry padrão
        value_entry = tk.Entry(value_frame, bg="#0f3460", fg=self.colors["text"],
                              relief="flat", width=40)
        value_entry.insert(0, cmd['value'])
        value_entry.pack()
        
        # Combobox para teclas
        value_combo = ttk.Combobox(value_frame, values=self.available_keys, width=37)
        
        # Parsear teclas modificadoras do valor existente
        ctrl_var = tk.BooleanVar()
        alt_var = tk.BooleanVar()
        shift_var = tk.BooleanVar()
        
        if cmd['type'] == "key" and "+" in cmd['value']:
            parts = cmd['value'].split("+")
            base_key = parts[-1]
            modifiers = parts[:-1]
            
            ctrl_var.set("ctrl" in modifiers)
            alt_var.set("alt" in modifiers)
            shift_var.set("shift" in modifiers)
            value_combo.set(base_key)
        elif cmd['type'] == "key":
            value_combo.set(cmd['value'])
        
        # Frame para teclas adicionais (modificadores)
        key_modifiers_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        tk.Label(key_modifiers_frame, text="Teclas adicionais:", bg=self.colors["bg"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack()
        
        mod_frame = tk.Frame(key_modifiers_frame, bg=self.colors["bg"])
        mod_frame.pack()
        
        tk.Checkbutton(mod_frame, text="Ctrl", variable=ctrl_var, bg=self.colors["bg"],
                      fg=self.colors["text"], selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Checkbutton(mod_frame, text="Alt", variable=alt_var, bg=self.colors["bg"],
                      fg=self.colors["text"], selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Checkbutton(mod_frame, text="Shift", variable=shift_var, bg=self.colors["bg"],
                      fg=self.colors["text"], selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        # Opção de ação da tecla
        key_action_frame = tk.Frame(key_modifiers_frame, bg=self.colors["bg"])
        key_action_frame.pack(pady=5)
        
        tk.Label(key_action_frame, text="Ação da tecla:", bg=self.colors["bg"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=5)
        
        existing_key_action = cmd.get('options', {}).get('key_action', 'normal')
        key_action_var = tk.StringVar(value=existing_key_action)
        
        tk.Radiobutton(key_action_frame, text="Normal", variable=key_action_var, value="normal",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(key_action_frame, text="Pressionar", variable=key_action_var, value="down",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(key_action_frame, text="Liberar", variable=key_action_var, value="up",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        # Opção para segurar tecla
        hold_frame = tk.Frame(key_modifiers_frame, bg=self.colors["bg"])
        hold_frame.pack(pady=5)
        
        hold_key_var = tk.BooleanVar(value=cmd.get('options', {}).get('hold_time', 0) > 0)
        tk.Checkbutton(hold_frame, text="Segurar tecla por", variable=hold_key_var,
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        hold_time_entry = tk.Entry(hold_frame, bg="#0f3460", fg=self.colors["text"],
                                  relief="flat", width=8)
        hold_time_entry.insert(0, str(cmd.get('options', {}).get('hold_time', 1.0)))
        hold_time_entry.pack(side="left", padx=5)
        
        tk.Label(hold_frame, text="segundos", bg=self.colors["bg"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=2)
        
        # Seletor de imagens (para edição)
        image_selector_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        
        # Combobox com imagens existentes
        image_combo = ttk.Combobox(image_selector_frame, values=[], state="readonly", width=28)
        image_combo.pack(side="left", padx=5)
        
        def refresh_images():
            folder = self.bot.config.data["folder"]
            if os.path.exists(folder):
                images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
                image_combo['values'] = images
                if cmd['type'] in ["click_image", "click_all", "wait_image", "if_image"] and cmd['value'] in images:
                    image_combo.set(cmd['value'])
                elif images:
                    image_combo.set(images[0])
        
        tk.Button(image_selector_frame, text="🔄", command=refresh_images,
                 bg=self.colors["accent"], fg=self.colors["text"],
                 relief="flat", cursor="hand2", width=2).pack(side="left", padx=2)
        
        # Botão para escolher imagem do computador
        def select_image_file():
            filepath = filedialog.askopenfilename(
                title="Selecionar Imagem",
                filetypes=[
                    ("Imagens", "*.png *.jpg *.jpeg *.bmp"),
                    ("PNG", "*.png"),
                    ("JPEG", "*.jpg *.jpeg"),
                    ("Todos os arquivos", "*.*")
                ]
            )
            
            if filepath:
                try:
                    import shutil
                    folder = self.bot.config.data["folder"]
                    if not os.path.exists(folder):
                        os.makedirs(folder)
                    
                    filename = os.path.basename(filepath)
                    if os.path.exists(os.path.join(folder, filename)):
                        name, ext = os.path.splitext(filename)
                        filename = f"{name}_{int(time.time())}{ext}"
                    
                    dest_path = os.path.join(folder, filename)
                    shutil.copy2(filepath, dest_path)
                    
                    refresh_images()
                    image_combo.set(filename)
                    messagebox.showinfo("Sucesso", f"Imagem importada: {filename}")
                    
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao importar imagem: {e}")
        
        tk.Button(image_selector_frame, text="📁", command=select_image_file,
                 bg=self.colors["success"], fg="#000",
                 relief="flat", cursor="hand2", width=2,
                 font=("Arial", 10, "bold")).pack(side="left", padx=2)
        
        tk.Label(image_selector_frame, text="Escolher imagem",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        # Seletor de pasta (para edição)
        folder_selector_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        
        folder_path_var = tk.StringVar(value=cmd['value'] if cmd['type'] == 'click_folder' else "")
        folder_entry = tk.Entry(folder_selector_frame, textvariable=folder_path_var,
                               bg="#0f3460", fg=self.colors["text"], relief="flat", width=28)
        folder_entry.pack(side="left", padx=5)
        
        def select_folder_path():
            folder = filedialog.askdirectory(title="Selecionar Pasta com Imagens")
            if folder:
                folder_path_var.set(folder)
        
        tk.Button(folder_selector_frame, text="📁", command=select_folder_path,
                 bg=self.colors["success"], fg="#000",
                 relief="flat", cursor="hand2", width=2,
                 font=("Arial", 10, "bold")).pack(side="left", padx=2)
        
        tk.Label(folder_selector_frame, text="Pasta com imagens",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        # Frame para SE/SENAO
        se_senao_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        
        tk.Label(se_senao_frame, text="Tipo de Condição:", bg=self.colors["bg"],
                fg=self.colors["text"], font=("Arial", 9)).pack(anchor="w", padx=10, pady=(5, 2))
        
        existing_condition_type = cmd.get('options', {}).get('condition_type', 'image')
        condition_type_var = tk.StringVar(value=existing_condition_type)
        
        image_radio = tk.Radiobutton(se_senao_frame, text="Verificar Imagem", variable=condition_type_var,
                      value="image", bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"])
        image_radio.pack(anchor="w", padx=20)
        
        multi_image_radio = tk.Radiobutton(se_senao_frame, text="Verificar Múltiplas Imagens (qualquer uma)", variable=condition_type_var,
                      value="multi_image", bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"])
        multi_image_radio.pack(anchor="w", padx=20)
        
        text_radio = tk.Radiobutton(se_senao_frame, text="Verificar Texto (OCR)", variable=condition_type_var,
                      value="text", bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"])
        text_radio.pack(anchor="w", padx=20)
        
        # Frame para seletor de imagem única
        se_image_frame = tk.Frame(se_senao_frame, bg=self.colors["bg"])
        se_image_frame.pack(anchor="w", padx=20, pady=5, fill="x")
        
        se_image_combo = ttk.Combobox(se_image_frame, values=[], state="readonly", width=28)
        se_image_combo.pack(side="left", padx=2)
        
        def refresh_se_images():
            folder = self.bot.config.data["folder"]
            if os.path.exists(folder):
                images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
                se_image_combo['values'] = images
                if cmd['type'] == 'se' and existing_condition_type == 'image' and cmd['value'] in images:
                    se_image_combo.set(cmd['value'])
                elif images:
                    se_image_combo.set(images[0])
        
        tk.Button(se_image_frame, text="🔄", command=refresh_se_images,
                 bg=self.colors["accent"], fg=self.colors["text"],
                 relief="flat", cursor="hand2", width=2).pack(side="left", padx=2)
        
        def select_se_image_file():
            filepath = filedialog.askopenfilename(
                title="Selecionar Imagem",
                filetypes=[
                    ("Imagens", "*.png *.jpg *.jpeg *.bmp"),
                    ("PNG", "*.png"),
                    ("JPEG", "*.jpg *.jpeg"),
                    ("Todos os arquivos", "*.*")
                ]
            )
            
            if filepath:
                try:
                    import shutil
                    folder = self.bot.config.data["folder"]
                    if not os.path.exists(folder):
                        os.makedirs(folder)
                    
                    filename = os.path.basename(filepath)
                    if os.path.exists(os.path.join(folder, filename)):
                        name, ext = os.path.splitext(filename)
                        filename = f"{name}_{int(time.time())}{ext}"
                    
                    dest_path = os.path.join(folder, filename)
                    shutil.copy2(filepath, dest_path)
                    
                    refresh_se_images()
                    se_image_combo.set(filename)
                    messagebox.showinfo("Sucesso", f"Imagem importada: {filename}")
                    
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao importar imagem: {e}")
        
        tk.Button(se_image_frame, text="📁", command=select_se_image_file,
                 bg=self.colors["success"], fg="#000",
                 relief="flat", cursor="hand2", width=2,
                 font=("Arial", 10, "bold")).pack(side="left", padx=2)
        
        tk.Label(se_image_frame, text="Carregar",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        # Frame para múltiplas imagens
        se_multi_image_frame = tk.Frame(se_senao_frame, bg=self.colors["bg"])
        se_multi_image_frame.pack(anchor="w", padx=20, pady=5, fill="both")
        
        tk.Label(se_multi_image_frame, text="Pasta com imagens:",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 8)).pack(anchor="w", pady=2)
        
        # Frame com entry e botão
        multi_folder_frame = tk.Frame(se_multi_image_frame, bg=self.colors["bg"])
        multi_folder_frame.pack(fill="x", pady=2)
        
        existing_multi_folder = cmd['value'] if cmd['type'] == 'se' and existing_condition_type == 'multi_image' else ""
        se_multi_folder_var = tk.StringVar(value=existing_multi_folder)
        se_multi_folder_entry = tk.Entry(multi_folder_frame, textvariable=se_multi_folder_var,
                                        bg="#0f3460", fg=self.colors["text"], 
                                        relief="flat", width=35)
        se_multi_folder_entry.pack(side="left", padx=2)
        
        def select_multi_folder():
            folder = filedialog.askdirectory(title="Selecionar Pasta com Imagens")
            if folder:
                se_multi_folder_var.set(folder)
                # Conta e mostra quantas imagens
                try:
                    images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
                    se_multi_info_label.config(text=f"✓ {len(images)} imagens encontradas")
                except:
                    se_multi_info_label.config(text="✗ Erro ao ler pasta")
        
        tk.Button(multi_folder_frame, text="📁 Selecionar Pasta", 
                 command=select_multi_folder,
                 bg=self.colors["success"], fg="#000",
                 relief="flat", cursor="hand2",
                 font=("Arial", 9, "bold"), padx=10, pady=3).pack(side="left", padx=2)
        
        se_multi_info_label = tk.Label(se_multi_image_frame, text="Nenhuma pasta selecionada",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7))
        se_multi_info_label.pack(anchor="w", pady=2)
        
        # Atualiza label se já tiver pasta selecionada
        if existing_multi_folder and os.path.exists(existing_multi_folder):
            try:
                images = [f for f in os.listdir(existing_multi_folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
                se_multi_info_label.config(text=f"✓ {len(images)} imagens encontradas")
            except:
                se_multi_info_label.config(text="✗ Erro ao ler pasta")
        
        # Frame para entrada de texto
        se_text_frame = tk.Frame(se_senao_frame, bg=self.colors["bg"])
        se_text_frame.pack(anchor="w", padx=20, pady=5, fill="x")
        
        se_value_entry = tk.Entry(se_text_frame, bg="#0f3460", fg=self.colors["text"],
                                 relief="flat", width=40)
        if cmd['type'] == 'se' and existing_condition_type == 'text':
            se_value_entry.insert(0, cmd['value'])
        se_value_entry.pack(side="left", padx=2)
        
        tk.Label(se_text_frame, text="Digite o texto ou selecione imagem acima",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        def update_se_inputs(*args):
            """Mostra/esconde inputs baseado no tipo de condição"""
            cond_type = condition_type_var.get()
            if cond_type == "image":
                se_image_frame.pack(anchor="w", padx=20, pady=5, fill="x")
                se_multi_image_frame.pack_forget()
                se_text_frame.pack_forget()
            elif cond_type == "multi_image":
                se_image_frame.pack_forget()
                se_multi_image_frame.pack(anchor="w", padx=20, pady=5, fill="both")
                se_text_frame.pack_forget()
            else:  # text
                se_text_frame.pack(anchor="w", padx=20, pady=5, fill="x")
                se_image_frame.pack_forget()
                se_multi_image_frame.pack_forget()
        
        condition_type_var.trace("w", update_se_inputs)
        
        # Inicializa carregando imagens
        refresh_se_images()
        update_se_inputs()
        
        # Frame para arrastar (drag) - edição
        drag_frame_edit = tk.Frame(value_frame, bg=self.colors["bg"])
        
        # Coordenadas de início
        start_frame_edit = tk.Frame(drag_frame_edit, bg=self.colors["bg"])
        start_frame_edit.pack(pady=2)
        
        tk.Label(start_frame_edit, text="Início:", bg=self.colors["bg"], fg=self.colors["text"],
                font=("Arial", 9)).pack(side="left", padx=5)
        
        start_coord_entry_edit = tk.Entry(start_frame_edit, bg="#0f3460", fg=self.colors["text"],
                                         relief="flat", width=15)
        start_coord_entry_edit.pack(side="left", padx=5)
        
        # Label para mostrar posição atual (início - edição)
        start_pos_label_edit = tk.Label(start_frame_edit, text="(0, 0)", bg=self.colors["bg"],
                                       fg=self.colors["warning"], font=("Arial", 9))
        start_pos_label_edit.pack(side="left", padx=5)
        
        # Estado de captura para coordenada de início (edição)
        capturing_start_edit = {"active": False}
        
        def update_start_mouse_pos_edit():
            if capturing_start_edit["active"]:
                x, y = pyautogui.position()
                start_pos_label_edit.config(text=f"({x}, {y})")
                dialog.after(50, update_start_mouse_pos_edit)
        
        def toggle_start_capture_edit():
            if not capturing_start_edit["active"]:
                capturing_start_edit["active"] = True
                start_capture_btn_edit.config(text="⏹ Parar (Alt)", bg=self.colors["primary"])
                update_start_mouse_pos_edit()
                
                def on_alt_press_start_edit(e):
                    if capturing_start_edit["active"]:
                        x, y = pyautogui.position()
                        start_coord_entry_edit.delete(0, tk.END)
                        start_coord_entry_edit.insert(0, f"{x},{y}")
                        capturing_start_edit["active"] = False
                        start_capture_btn_edit.config(text="📍 Capturar", bg=self.colors["success"])
                        start_pos_label_edit.config(text="(0, 0)")
                        dialog.unbind("<Alt_L>")
                        dialog.unbind("<Alt_R>")
                
                dialog.bind("<Alt_L>", on_alt_press_start_edit)
                dialog.bind("<Alt_R>", on_alt_press_start_edit)
            else:
                capturing_start_edit["active"] = False
                start_capture_btn_edit.config(text="📍 Capturar", bg=self.colors["success"])
                start_pos_label_edit.config(text="(0, 0)")
        
        start_capture_btn_edit = tk.Button(start_frame_edit, text="📍 Capturar",
                                          command=toggle_start_capture_edit,
                                          bg=self.colors["success"], fg="#000", relief="flat",
                                          cursor="hand2", font=("Arial", 8))
        start_capture_btn_edit.pack(side="left", padx=2)
        
        # Coordenadas de fim
        end_frame_edit = tk.Frame(drag_frame_edit, bg=self.colors["bg"])
        end_frame_edit.pack(pady=2)
        
        tk.Label(end_frame_edit, text="Fim:", bg=self.colors["bg"], fg=self.colors["text"],
                font=("Arial", 9)).pack(side="left", padx=5)
        
        end_coord_entry_edit = tk.Entry(end_frame_edit, bg="#0f3460", fg=self.colors["text"],
                                       relief="flat", width=15)
        end_coord_entry_edit.pack(side="left", padx=5)
        
        # Label para mostrar posição atual (fim - edição)
        end_pos_label_edit = tk.Label(end_frame_edit, text="(0, 0)", bg=self.colors["bg"],
                                     fg=self.colors["warning"], font=("Arial", 9))
        end_pos_label_edit.pack(side="left", padx=5)
        
        # Estado de captura para coordenada de fim (edição)
        capturing_end_edit = {"active": False}
        
        def update_end_mouse_pos_edit():
            if capturing_end_edit["active"]:
                x, y = pyautogui.position()
                end_pos_label_edit.config(text=f"({x}, {y})")
                dialog.after(50, update_end_mouse_pos_edit)
        
        def toggle_end_capture_edit():
            if not capturing_end_edit["active"]:
                capturing_end_edit["active"] = True
                end_capture_btn_edit.config(text="⏹ Parar (Alt)", bg=self.colors["primary"])
                update_end_mouse_pos_edit()
                
                def on_alt_press_end_edit(e):
                    if capturing_end_edit["active"]:
                        x, y = pyautogui.position()
                        end_coord_entry_edit.delete(0, tk.END)
                        end_coord_entry_edit.insert(0, f"{x},{y}")
                        capturing_end_edit["active"] = False
                        end_capture_btn_edit.config(text="📍 Capturar", bg=self.colors["success"])
                        end_pos_label_edit.config(text="(0, 0)")
                        dialog.unbind("<Alt_L>")
                        dialog.unbind("<Alt_R>")
                
                dialog.bind("<Alt_L>", on_alt_press_end_edit)
                dialog.bind("<Alt_R>", on_alt_press_end_edit)
            else:
                capturing_end_edit["active"] = False
                end_capture_btn_edit.config(text="📍 Capturar", bg=self.colors["success"])
                end_pos_label_edit.config(text="(0, 0)")
        
        end_capture_btn_edit = tk.Button(end_frame_edit, text="📍 Capturar",
                                        command=toggle_end_capture_edit,
                                        bg=self.colors["success"], fg="#000", relief="flat",
                                        cursor="hand2", font=("Arial", 8))
        end_capture_btn_edit.pack(side="left", padx=2)
        
        # Opções do mouse
        mouse_frame_edit = tk.Frame(drag_frame_edit, bg=self.colors["bg"])
        mouse_frame_edit.pack(pady=5)
        
        tk.Label(mouse_frame_edit, text="Botão:", bg=self.colors["bg"], fg=self.colors["text"],
                font=("Arial", 9)).pack(side="left", padx=5)
        
        drag_button_var_edit = tk.StringVar(value="left")
        tk.Radiobutton(mouse_frame_edit, text="Esquerdo", variable=drag_button_var_edit, value="left",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(mouse_frame_edit, text="Direito", variable=drag_button_var_edit, value="right",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        # Frame para coordenadas
        coord_frame = tk.Frame(value_frame, bg=self.colors["bg"])
        coord_entry = tk.Entry(coord_frame, bg="#0f3460", fg=self.colors["text"],
                              relief="flat", width=25)
        coord_entry.pack(side="left", padx=5)
        
        if cmd['type'] in ["move_mouse", "click_pos"]:
            coord_entry.insert(0, cmd['value'])
        else:
            coord_entry.insert(0, "0,0")
        
        current_pos_label = tk.Label(coord_frame, text="(0, 0)", bg=self.colors["bg"],
                                     fg=self.colors["warning"], font=("Arial", 9))
        current_pos_label.pack(side="left", padx=5)
        
        capturing_coords = {"active": False}
        
        def update_mouse_pos():
            if capturing_coords["active"]:
                x, y = pyautogui.position()
                current_pos_label.config(text=f"({x}, {y})")
                dialog.after(50, update_mouse_pos)
        
        def toggle_coord_capture():
            if not capturing_coords["active"]:
                capturing_coords["active"] = True
                capture_btn.config(text="⏹ Parar (Alt)", bg=self.colors["primary"])
                update_mouse_pos()
                
                def on_alt_press(e):
                    if capturing_coords["active"]:
                        x, y = pyautogui.position()
                        coord_entry.delete(0, tk.END)
                        coord_entry.insert(0, f"{x},{y}")
                        capturing_coords["active"] = False
                        capture_btn.config(text="📍 Capturar Posição", bg=self.colors["success"])
                        dialog.unbind("<Alt_L>")
                        dialog.unbind("<Alt_R>")
                
                dialog.bind("<Alt_L>", on_alt_press)
                dialog.bind("<Alt_R>", on_alt_press)
            else:
                capturing_coords["active"] = False
                capture_btn.config(text="📍 Capturar Posição", bg=self.colors["success"])
        
        capture_btn = tk.Button(coord_frame, text="📍 Capturar Posição",
                               command=toggle_coord_capture,
                               bg=self.colors["success"], fg="#000",
                               relief="flat", cursor="hand2", font=("Arial", 8))
        capture_btn.pack(side="left", padx=5)
        
        tk.Label(coord_frame, text="Mova o mouse e pressione Alt",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=5)
        
        tk.Label(folder_selector_frame, text="Pasta com imagens",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        # Frame para comando STOP (edição)
        stop_frame_edit = tk.Frame(value_frame, bg=self.colors["bg"])
        
        tk.Label(stop_frame_edit, text="Tipo de Validação:", bg=self.colors["bg"],
                fg=self.colors["text"], font=("Arial", 9)).pack(anchor="w", padx=10, pady=(5, 2))
        
        existing_stop_type = cmd.get('options', {}).get('stop_type', 'image')
        stop_type_var_edit = tk.StringVar(value=existing_stop_type)
        
        stop_image_radio_edit = tk.Radiobutton(stop_frame_edit, text="Parar quando encontrar Imagem", 
                      variable=stop_type_var_edit, value="image",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"])
        stop_image_radio_edit.pack(anchor="w", padx=20)
        
        stop_text_radio_edit = tk.Radiobutton(stop_frame_edit, text="Parar quando encontrar Texto (OCR)", 
                      variable=stop_type_var_edit, value="text",
                      bg=self.colors["bg"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"])
        stop_text_radio_edit.pack(anchor="w", padx=20)
        
        # Frame para seletor de imagem do stop (edição)
        stop_image_frame_edit = tk.Frame(stop_frame_edit, bg=self.colors["bg"])
        stop_image_frame_edit.pack(anchor="w", padx=20, pady=5, fill="x")
        
        stop_image_combo_edit = ttk.Combobox(stop_image_frame_edit, values=[], state="readonly", width=28)
        stop_image_combo_edit.pack(side="left", padx=2)
        
        def refresh_stop_images_edit():
            folder = self.bot.config.data["folder"]
            if os.path.exists(folder):
                images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))]
                stop_image_combo_edit['values'] = images
                if cmd['type'] == 'stop' and existing_stop_type == 'image' and cmd['value'] in images:
                    stop_image_combo_edit.set(cmd['value'])
                elif images:
                    stop_image_combo_edit.set(images[0])
        
        tk.Button(stop_image_frame_edit, text="🔄", command=refresh_stop_images_edit,
                 bg=self.colors["accent"], fg=self.colors["text"],
                 relief="flat", cursor="hand2", width=2).pack(side="left", padx=2)
        
        # Frame para entrada de texto do stop (edição)
        stop_text_frame_edit = tk.Frame(stop_frame_edit, bg=self.colors["bg"])
        stop_text_frame_edit.pack(anchor="w", padx=20, pady=5, fill="x")
        
        stop_text_entry_edit = tk.Entry(stop_text_frame_edit, bg="#0f3460", fg=self.colors["text"],
                                  relief="flat", width=40)
        if cmd['type'] == 'stop' and existing_stop_type == 'text':
            stop_text_entry_edit.insert(0, cmd['value'])
        stop_text_entry_edit.pack(side="left", padx=2)
        
        tk.Label(stop_text_frame_edit, text="Digite o texto ou selecione imagem acima",
                bg=self.colors["bg"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=3)
        
        def update_stop_inputs_edit(*args):
            """Mostra/esconde inputs baseado no tipo de validação"""
            val_type = stop_type_var_edit.get()
            if val_type == "image":
                stop_image_frame_edit.pack(anchor="w", padx=20, pady=5, fill="x")
                stop_text_frame_edit.pack_forget()
            else:  # text
                stop_text_frame_edit.pack(anchor="w", padx=20, pady=5, fill="x")
                stop_image_frame_edit.pack_forget()
        
        stop_type_var_edit.trace("w", update_stop_inputs_edit)
        if cmd['type'] == 'stop':
            refresh_stop_images_edit()
            update_stop_inputs_edit()
        
        def on_type_change(*args):
            cmd_type = self.cmd_display[type_var.get()]
            
            # Esconde tudo
            value_entry.pack_forget()
            value_combo.pack_forget()
            key_modifiers_frame.pack_forget()
            image_selector_frame.pack_forget()
            folder_selector_frame.pack_forget()
            drag_frame_edit.pack_forget()
            coord_frame.pack_forget()
            se_senao_frame.pack_forget()
            stop_frame_edit.pack_forget()
            
            # Não ajusta mais o tamanho, mantém fixo em 550px
            if cmd_type == "key":
                value_combo.pack()
                key_modifiers_frame.pack(pady=5)
            elif cmd_type == "click_image":
                refresh_images()
                image_selector_frame.pack()
            elif cmd_type == "click_folder":
                folder_selector_frame.pack()
            elif cmd_type == "se":
                se_senao_frame.pack(anchor="w", padx=0, pady=5)
            elif cmd_type == "stop":
                stop_frame_edit.pack(anchor="w", padx=0, pady=5)
            elif cmd_type in ["senao", "fim"]:
                # SENAO e FIM não precisam de valor
                pass
            elif cmd_type == "drag":
                drag_frame_edit.pack()
            elif cmd_type in ["move_mouse", "click_pos"]:
                coord_frame.pack()
            else:
                value_entry.pack()
        
        type_var.trace("w", on_type_change)
        
        # Inicializa os campos corretos baseado no tipo atual
        if cmd['type'] == 'se':
            refresh_se_images()
            update_se_inputs()
        elif cmd['type'] == 'stop':
            refresh_stop_images_edit()
            update_stop_inputs_edit()
        
        on_type_change()  # Chama uma vez para configurar a interface
        
        # Inicializar valores para comando drag existente
        if cmd['type'] == 'drag':
            coords = cmd['value'].split(',') if ',' in cmd['value'] else ['0,0', '100,100']
            if len(coords) >= 4:
                start_coord_entry_edit.insert(0, f"{coords[0]},{coords[1]}")
                end_coord_entry_edit.insert(0, f"{coords[2]},{coords[3]}")
            else:
                start_coord_entry_edit.insert(0, "0,0")
                end_coord_entry_edit.insert(0, "100,100")
            
            # Inicializar botão do mouse
            drag_button_var_edit.set(cmd.get('options', {}).get('button', 'left'))
        
        tk.Label(dialog, text="Delay após comando (s):", bg=self.colors["bg"],
                fg=self.colors["text"]).pack(pady=(10, 0))
        delay_entry = tk.Entry(dialog, bg="#0f3460", fg=self.colors["text"],
                              relief="flat", width=10)
        delay_entry.insert(0, str(cmd.get('delay', 0)))
        delay_entry.pack(pady=5)
        
        # Frame de opções extras (visível apenas para comandos de clique)
        extras_frame_edit = tk.Frame(dialog, bg=self.colors["bg"])
        
        # Opções de clique variável
        tk.Label(extras_frame_edit, text="Opções extras:", bg=self.colors["bg"],
                fg=self.colors["text"], font=("Arial", 9, "bold")).pack(pady=(10, 0))
        
        click_options_frame_edit = tk.Frame(extras_frame_edit, bg=self.colors["bg_light"], relief="groove", borderwidth=2)
        click_options_frame_edit.pack(pady=5, padx=20, fill="x")
        
        tk.Label(click_options_frame_edit, text="🎯 Posição de Clique:", bg=self.colors["bg_light"],
                fg=self.colors["text"], font=("Arial", 9, "bold")).pack(pady=5)
        
        # Carregar valores existentes
        existing_mode = cmd.get('options', {}).get('click_mode', 'fixed')
        existing_radius = cmd.get('options', {}).get('click_radius', 5)
        existing_button = cmd.get('options', {}).get('button', 'left')
        existing_hold = cmd.get('options', {}).get('hold_time', 0)
        
        click_mode_var = tk.StringVar(value=existing_mode)
        
        fixed_radio = tk.Radiobutton(click_options_frame_edit, text="Fixa (sempre no centro)", 
                                    variable=click_mode_var, value="fixed",
                                    bg=self.colors["bg_light"], fg=self.colors["text"],
                                    selectcolor=self.colors["accent"])
        fixed_radio.pack(anchor="w", padx=10)
        
        variable_radio = tk.Radiobutton(click_options_frame_edit, text="Variável (aleatório ao redor)", 
                                       variable=click_mode_var, value="variable",
                                       bg=self.colors["bg_light"], fg=self.colors["text"],
                                       selectcolor=self.colors["accent"])
        variable_radio.pack(anchor="w", padx=10)
        
        radius_frame = tk.Frame(click_options_frame_edit, bg=self.colors["bg_light"])
        radius_frame.pack(pady=5, padx=20, fill="x")
        
        tk.Label(radius_frame, text="Raio de variação (pixels):", bg=self.colors["bg_light"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=5)
        
        radius_var = tk.IntVar(value=existing_radius)
        radius_spinbox = tk.Spinbox(radius_frame, from_=1, to=50, textvariable=radius_var,
                                   bg="#0f3460", fg=self.colors["text"], width=8,
                                   relief="flat", state="disabled" if existing_mode == "fixed" else "normal")
        radius_spinbox.pack(side="left", padx=5)
        
        tk.Label(radius_frame, text="(quanto maior, mais disperso o clique)", 
                bg=self.colors["bg_light"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=5)
        
        def toggle_radius_spinbox(*args):
            if click_mode_var.get() == "variable":
                radius_spinbox.config(state="normal")
            else:
                radius_spinbox.config(state="disabled")
        
        click_mode_var.trace("w", toggle_radius_spinbox)
        
        # Opção de botão do mouse
        mouse_button_frame = tk.Frame(click_options_frame_edit, bg=self.colors["bg_light"])
        mouse_button_frame.pack(pady=5, padx=20, fill="x")
        
        tk.Label(mouse_button_frame, text="Botão do mouse:", bg=self.colors["bg_light"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=5)
        
        mouse_button_var = tk.StringVar(value=existing_button)
        
        tk.Radiobutton(mouse_button_frame, text="Esquerdo", variable=mouse_button_var, value="left",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(mouse_button_frame, text="Direito", variable=mouse_button_var, value="right",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(mouse_button_frame, text="Meio", variable=mouse_button_var, value="middle",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        # Opção de ação do clique (edição)
        click_action_frame_edit = tk.Frame(click_options_frame_edit, bg=self.colors["bg_light"])
        click_action_frame_edit.pack(pady=5, padx=20, fill="x")
        
        tk.Label(click_action_frame_edit, text="Ação do clique:", bg=self.colors["bg_light"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=5)
        
        existing_click_action = cmd.get('options', {}).get('click_action', 'normal')
        click_action_var = tk.StringVar(value=existing_click_action)
        
        tk.Radiobutton(click_action_frame_edit, text="Normal", variable=click_action_var, value="normal",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(click_action_frame_edit, text="Pressionar", variable=click_action_var, value="down",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        tk.Radiobutton(click_action_frame_edit, text="Liberar", variable=click_action_var, value="up",
                      bg=self.colors["bg_light"], fg=self.colors["text"],
                      selectcolor=self.colors["accent"]).pack(side="left", padx=5)
        
        # Tempo de segurar botão
        hold_frame_edit = tk.Frame(click_options_frame_edit, bg=self.colors["bg_light"])
        hold_frame_edit.pack(pady=5, padx=20, fill="x")
        
        tk.Label(hold_frame_edit, text="Segurar botão (segundos):", bg=self.colors["bg_light"],
                fg=self.colors["text_dim"], font=("Arial", 8)).pack(side="left", padx=5)
        
        hold_time_var_edit = tk.DoubleVar(value=existing_hold)
        hold_spinbox_edit = tk.Spinbox(hold_frame_edit, from_=0, to=10, increment=0.1, 
                                       textvariable=hold_time_var_edit,
                                       bg="#0f3460", fg=self.colors["text"], width=8, relief="flat")
        hold_spinbox_edit.pack(side="left", padx=5)
        
        tk.Label(hold_frame_edit, text="(0 = clique normal)", 
                bg=self.colors["bg_light"], fg=self.colors["text_dim"],
                font=("Arial", 7)).pack(side="left", padx=5)
        
        # Mostrar/esconder opções baseado no tipo
        def update_extras_visibility_edit(*args):
            cmd_type = self.cmd_display.get(type_var.get(), "")
            
            if cmd_type in ["click_image", "click_folder", "click", "click_pos"]:
                extras_frame_edit.pack(fill="x", pady=5)
            else:
                extras_frame_edit.pack_forget()
        
        type_var.trace("w", update_extras_visibility_edit)
        update_extras_visibility_edit()  # Chama uma vez para configurar
        
        def save():
            try:
                display_type = type_var.get()
                cmd['type'] = self.cmd_display[display_type]
                
                # Pega valor apropriado
                if cmd['type'] == "key":
                    base_key = value_combo.get()
                    modifiers = []
                    if ctrl_var.get():
                        modifiers.append("ctrl")
                    if alt_var.get():
                        modifiers.append("alt")
                    if shift_var.get():
                        modifiers.append("shift")
                    
                    if modifiers:
                        cmd['value'] = "+".join(modifiers) + "+" + base_key
                    else:
                        cmd['value'] = base_key
                elif cmd['type'] == "click_image":
                    cmd['value'] = image_combo.get()
                    if not cmd['value']:
                        messagebox.showwarning("Aviso", "Selecione uma imagem!")
                        return
                elif cmd['type'] == "click_folder":
                    cmd['value'] = folder_path_var.get()
                    if not cmd['value']:
                        messagebox.showwarning("Aviso", "Selecione uma pasta!")
                        return
                elif cmd['type'] == "se":
                    condition_type = condition_type_var.get()
                    if condition_type == "image":
                        cmd['value'] = se_image_combo.get()
                        if not cmd['value']:
                            messagebox.showwarning("Aviso", "Selecione uma imagem para a condição SE!")
                            return
                    elif condition_type == "multi_image":
                        cmd['value'] = se_multi_folder_var.get()
                        if not cmd['value']:
                            messagebox.showwarning("Aviso", "Selecione uma pasta com imagens!")
                            return
                        if not os.path.exists(cmd['value']):
                            messagebox.showwarning("Aviso", "A pasta selecionada não existe!")
                            return
                    else:  # text
                        cmd['value'] = se_value_entry.get().strip()
                        if not cmd['value']:
                            messagebox.showwarning("Aviso", "Digite o texto para a condição SE!")
                            return
                elif cmd['type'] == "senao":
                    # SENAO não precisa de valor
                    cmd['value'] = ""
                elif cmd['type'] == "fim":
                    # FIM não precisa de valor
                    cmd['value'] = ""
                elif cmd['type'] == "stop":
                    val_type = stop_type_var_edit.get()
                    if val_type == "image":
                        cmd['value'] = stop_image_combo_edit.get()
                        if not cmd['value']:
                            messagebox.showwarning("Aviso", "Selecione uma imagem para validação!")
                            return
                    else:  # text
                        cmd['value'] = stop_text_entry_edit.get().strip()
                        if not cmd['value']:
                            messagebox.showwarning("Aviso", "Digite o texto para validação!")
                            return
                elif cmd['type'] == "drag":
                    start_coords = start_coord_entry_edit.get().strip()
                    end_coords = end_coord_entry_edit.get().strip()
                    if not start_coords or not end_coords:
                        messagebox.showwarning("Aviso", "Defina as coordenadas de início e fim!")
                        return
                    cmd['value'] = f"{start_coords},{end_coords}"
                elif cmd['type'] in ["move_mouse", "click_pos"]:
                    cmd['value'] = coord_entry.get().strip()
                else:
                    cmd['value'] = value_entry.get().strip()
                
                cmd['delay'] = float(delay_entry.get())
                
                cmd['options'] = {}
                
                # Adiciona opções específicas do comando
                if cmd['type'] == "key":
                    if hold_key_var.get():
                        try:
                            hold_time = float(hold_time_entry.get())
                            cmd['options']["hold_time"] = hold_time
                        except ValueError:
                            messagebox.showwarning("Aviso", "Tempo de duração inválido!")
                            return
                    cmd['options']["key_action"] = key_action_var.get()
                elif cmd['type'] == "se":
                    cmd['options']["condition_type"] = condition_type_var.get()
                elif cmd['type'] == "stop":
                    cmd['options']["stop_type"] = stop_type_var_edit.get()
                elif cmd['type'] in ["click_image", "click_folder", "click", "click_pos"]:
                    cmd['options']["click_mode"] = click_mode_var.get()
                    if click_mode_var.get() == "variable":
                        cmd['options']["click_radius"] = radius_var.get()
                    cmd['options']["button"] = mouse_button_var.get()
                    cmd['options']["hold_time"] = hold_time_var_edit.get()
                    cmd['options']["click_action"] = click_action_var.get()
                elif cmd['type'] == "drag":
                    cmd['options']["button"] = drag_button_var_edit.get()
                
                self.refresh_command_list()
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar: {e}")
        
        btn_frame = tk.Frame(dialog, bg=self.colors["bg"])
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="💾 Salvar", command=save,
                 bg=self.colors["success"], fg="#000", font=("Arial", 10, "bold"),
                 padx=30, pady=8, relief="flat", cursor="hand2").pack(side="left", padx=5)
        
        tk.Button(btn_frame, text="✗ Cancelar", command=dialog.destroy,
                 padx=30, pady=8, relief="flat", cursor="hand2").pack(side="left", padx=5)
    
    def save_commands(self):
        """Salva sequência de comandos"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(self.bot.commands, f, indent=4)
                messagebox.showinfo("Sucesso", "Comandos salvos com sucesso!")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar: {e}")
    
    def load_commands(self):
        """Carrega sequência de comandos"""
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível carregar comandos enquanto o macro está rodando!\nPause o macro primeiro.")
            return
        
        if self._loading:
            return
        
        self._loading = True
        try:
            filename = filedialog.askopenfilename(
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if filename:
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        self.bot.commands = json.load(f)
                    self.refresh_command_list()
                    messagebox.showinfo("Sucesso", "Comandos carregados com sucesso!")
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao carregar: {e}")
        finally:
            self._loading = False
    
    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)
    
    def save_config(self):
        """Salva configurações"""
        self.bot.config.data["folder"] = self.folder_var.get()
        self.bot.config.data["threshold"] = self.threshold_var.get()
        self.bot.config.data["delay_global"] = self.delay_var.get()
        self.bot.config.data["initial_delay"] = self.initial_delay_var.get()
        self.bot.config.data["loop_mode"] = self.loop_var.get()
        self.bot.config.data["loop_count"] = self.loop_count_var.get()
        self.bot.config.save()
    
    def toggle_loop_count(self):
        """Habilita/desabilita campo de repetições"""
        if self.loop_var.get() == "count":
            self.loop_count_entry.config(state="normal")
        else:
            self.loop_count_entry.config(state="disabled")
    
    def toggle_bot(self):
        """Alterna entre iniciar e pausar o bot"""
        if self.bot.running:
            self.stop_bot()
        else:
            self.start_bot()
    
    def start_bot(self):
        if self.bot.running:
            messagebox.showwarning("Aviso", "Bot já está rodando!")
            return
        
        if not self.bot.commands:
            messagebox.showwarning("Aviso", "Adicione comandos primeiro!")
            return
        
        self.save_config()
        self.bot.start()
        self.btn_start.config(text="⏸ PAUSAR", bg="#e94560", fg="#fff")
    
    def start_execution(self):
        """Inicia execução automática (para auto-start)"""
        if not self.bot.commands:
            self.add_log("⚠️ Nenhum comando para executar", "WARN")
            return
        
        self.save_config()
        self.bot.start()
        if hasattr(self, 'btn_start'):
            self.btn_start.config(text="⏸ PAUSAR", bg="#e94560", fg="#fff")
    
    def stop_bot(self):
        self.bot.stop()
        self.btn_start.config(text="▶ INICIAR", bg="#06ffa5", fg="#000")
    
    def setup_hotkeys(self):
        """Configura hotkeys globais"""
        try:
            keyboard.add_hotkey(self.bot.config.data["hotkey_start"], self.toggle_bot)
            keyboard.add_hotkey(self.bot.config.data["hotkey_record"], self.toggle_record)
            self.add_log("⌨ Hotkeys configuradas: F9=Iniciar/Pausar, F5=Gravar", "SUCCESS")
        except Exception as e:
            self.add_log(f"⚠ Erro ao configurar hotkeys: {e}", "WARN")
    
    # ==================== GRAVAÇÃO ====================
    def toggle_record(self):
        """Inicia ou para a gravação de comandos"""
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        """Inicia a gravação de comandos"""
        if self.bot.running:
            messagebox.showwarning("Aviso", "Não é possível gravar enquanto o macro está rodando!\nPause o macro primeiro.")
            return
        
        if not PYNPUT_AVAILABLE:
            messagebox.showerror("Erro", "Biblioteca pynput não encontrada!\nInstale com: pip install pynput")
            return
        
        try:
            self.recording = True
            self.recorded_commands = []
            self.last_record_time = time.time()
            self.mouse_press_times = {}
            self.key_press_times = {}
            self.btn_record.config(text="⏹ PARAR GRAVAÇÃO", bg="#e74c3c")
            self.add_log("🔴 Gravação iniciada! Clicando, digitando e capturando tempo...", "SUCCESS")
            self.add_log("💡 Pressione F5 novamente para parar a gravação.", "INFO")
            
            # Desativa as hotkeys temporariamente exceto F5
            keyboard.unhook_all()
            keyboard.add_hotkey(self.bot.config.data["hotkey_record"], self.toggle_record)
            
            def on_click(x, y, button, pressed):
                if not self.recording:
                    return
                
                # Mapeia o botão
                button_map = {
                    pynput_mouse.Button.left: "left",
                    pynput_mouse.Button.right: "right",
                    pynput_mouse.Button.middle: "middle"
                }
                button_name = button_map.get(button, "left")
                
                if pressed:  # Quando pressiona o botão
                    # Armazena o tempo em que o botão foi pressionado
                    self.mouse_press_times[button] = {
                        'time': time.time(),
                        'x': x,
                        'y': y
                    }
                    
                else:  # Quando solta o botão
                    if button in self.mouse_press_times:
                        press_info = self.mouse_press_times[button]
                        press_time = press_info['time']
                        hold_time = round(time.time() - press_time, 3)
                        
                        current_time = time.time()
                        delay = round(current_time - self.last_record_time, 2)
                        self.last_record_time = current_time
                        
                        cmd = {
                            "type": "click_pos",
                            "value": f"{press_info['x']},{press_info['y']}",
                            "delay": delay if len(self.recorded_commands) > 0 else 0,
                            "options": {
                                "button": button_name,
                                "click_mode": "fixed",
                                "click_action": "normal",
                                "hold_time": hold_time
                            }
                        }
                        self.recorded_commands.append(cmd)
                        self.add_log(f"🖱️ Click {button_name}: ({press_info['x']},{press_info['y']}) [segurado: {hold_time}s, delay: {delay}s]", "INFO")
                        
                        # Remove da lista de botões pressionados
                        del self.mouse_press_times[button]
            
            def on_key_press(key):
                if not self.recording:
                    return
                
                try:
                    # Tenta obter o nome da tecla
                    try:
                        key_name = key.char
                    except AttributeError:
                        # Teclas especiais
                        key_name = str(key).replace('Key.', '')
                    
                    # Ignora a tecla de gravação
                    if key_name == self.bot.config.data["hotkey_record"]:
                        return
                    
                    # Armazena o tempo e marca que foi pressionada
                    if key_name not in self.key_press_times:
                        current_time = time.time()
                        self.key_press_times[key_name] = {
                            'time': current_time,
                            'recorded_down': False
                        }
                        
                        # Checa após 0.5 segundo se ainda está pressionada
                        def check_still_pressed():
                            time.sleep(0.5)
                            if key_name in self.key_press_times and not self.key_press_times[key_name]['recorded_down']:
                                # Ainda está pressionada após 0.5s, registra como "down"
                                delay = round(time.time() - self.last_record_time, 2)
                                self.last_record_time = time.time()
                                
                                cmd_down = {
                                    "type": "key",
                                    "value": key_name,
                                    "delay": delay if len(self.recorded_commands) > 0 else 0,
                                    "options": {
                                        "key_action": "down"
                                    }
                                }
                                self.recorded_commands.append(cmd_down)
                                self.key_press_times[key_name]['recorded_down'] = True
                                self.add_log(f"⌨️ Tecla PRESSIONADA: {key_name}", "INFO")
                        
                        # Inicia thread para checar
                        threading.Thread(target=check_still_pressed, daemon=True).start()
                    
                except Exception as e:
                    pass
            
            def on_key_release(key):
                if not self.recording:
                    return
                
                try:
                    # Tenta obter o nome da tecla
                    try:
                        key_name = key.char
                    except AttributeError:
                        # Teclas especiais
                        key_name = str(key).replace('Key.', '')
                    
                    # Ignora a tecla de gravação
                    if key_name == self.bot.config.data["hotkey_record"]:
                        return
                    
                    # Calcula quanto tempo a tecla ficou pressionada
                    if key_name in self.key_press_times:
                        press_info = self.key_press_times[key_name]
                        press_time = press_info['time']
                        hold_time = round(time.time() - press_time, 3)
                        
                        current_time = time.time()
                        delay = round(current_time - self.last_record_time, 2)
                        self.last_record_time = current_time
                        
                        # Se foi registrado como "down" (segurou mais de 1s), agora registra o "up"
                        if press_info['recorded_down']:
                            cmd_up = {
                                "type": "key",
                                "value": key_name,
                                "delay": delay,
                                "options": {
                                    "key_action": "up"
                                }
                            }
                            self.recorded_commands.append(cmd_up)
                            self.add_log(f"⌨️ Tecla LIBERADA: {key_name}", "INFO")
                        else:
                            # Pressão normal (menos de 1 segundo) - pressiona e solta rápido
                            cmd = {
                                "type": "key",
                                "value": key_name,
                                "delay": delay if len(self.recorded_commands) > 0 else 0,
                                "options": {
                                    "key_action": "normal"
                                }
                            }
                            self.recorded_commands.append(cmd)
                            self.add_log(f"⌨️ Tecla: {key_name}", "INFO")
                        
                        # Remove da lista de teclas pressionadas
                        del self.key_press_times[key_name]
                    
                except Exception as e:
                    pass
            
            # Inicia os listeners
            self.mouse_listener = pynput_mouse.Listener(on_click=on_click)
            self.keyboard_listener = pynput_keyboard.Listener(
                on_press=on_key_press,
                on_release=on_key_release
            )
            
            self.mouse_listener.start()
            self.keyboard_listener.start()
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao iniciar gravação: {e}")
            self.recording = False
            self.btn_record.config(text="⏺ GRAVAR", bg="#ff6b6b")
    
    def stop_recording(self):
        """Para a gravação e adiciona os comandos gravados"""
        self.recording = False
        self.btn_record.config(text="⏺ GRAVAR", bg="#ff6b6b")
        
        # Para os listeners
        try:
            if hasattr(self, 'mouse_listener'):
                self.mouse_listener.stop()
            if hasattr(self, 'keyboard_listener'):
                self.keyboard_listener.stop()
        except:
            pass
        
        # Remove todas as hotkeys
        keyboard.unhook_all()
        
        # Reconfigura as hotkeys
        self.setup_hotkeys()
        
        # Adiciona os comandos gravados à lista
        if self.recorded_commands:
            self.bot.commands.extend(self.recorded_commands)
            self.refresh_command_list()
            self.add_log(f"✅ Gravação finalizada! {len(self.recorded_commands)} comandos adicionados.", "SUCCESS")
        else:
            self.add_log("⚠️ Nenhum comando foi gravado.", "WARN")
        
        self.recorded_commands = []
        self.last_record_time = None
    
    # ==================== JANELA DE CONFIGURAÇÕES ====================
    def open_settings(self):
        """Abre a janela de configurações"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Configurações")
        dialog.geometry("500x400")
        dialog.configure(bg=self.colors["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        
        self.position_dialog_window(dialog)
        
        tk.Label(dialog, text="⚙ CONFIGURAÇÕES", bg=self.colors["bg"],
                fg=self.colors["success"], font=("Arial", 14, "bold")).pack(pady=20)
        
        # Frame de configurações
        config_frame = tk.Frame(dialog, bg=self.colors["bg_light"], relief="groove", borderwidth=2)
        config_frame.pack(padx=20, pady=10, fill="both", expand=True)
        
        # Hotkeys
        tk.Label(config_frame, text="Teclas de Atalho:", bg=self.colors["bg_light"],
                fg=self.colors["text"], font=("Arial", 11, "bold")).pack(pady=10)
        
        # Grid para hotkeys
        hotkey_frame = tk.Frame(config_frame, bg=self.colors["bg_light"])
        hotkey_frame.pack(padx=20, pady=5)
        
        tk.Label(hotkey_frame, text="Iniciar:", bg=self.colors["bg_light"],
                fg=self.colors["text"]).grid(row=0, column=0, sticky="w", pady=5, padx=5)
        hotkey_start_var = tk.StringVar(value=self.bot.config.data["hotkey_start"])
        tk.Entry(hotkey_frame, textvariable=hotkey_start_var, bg="#0f3460",
                fg=self.colors["text"], relief="flat", width=10).grid(row=0, column=1, padx=5)
        
        tk.Label(hotkey_frame, text="Parar:", bg=self.colors["bg_light"],
                fg=self.colors["text"]).grid(row=1, column=0, sticky="w", pady=5, padx=5)
        hotkey_stop_var = tk.StringVar(value=self.bot.config.data["hotkey_stop"])
        tk.Entry(hotkey_frame, textvariable=hotkey_stop_var, bg="#0f3460",
                fg=self.colors["text"], relief="flat", width=10).grid(row=1, column=1, padx=5)
        
        tk.Label(hotkey_frame, text="Pausar:", bg=self.colors["bg_light"],
                fg=self.colors["text"]).grid(row=2, column=0, sticky="w", pady=5, padx=5)
        hotkey_pause_var = tk.StringVar(value=self.bot.config.data["hotkey_pause"])
        tk.Entry(hotkey_frame, textvariable=hotkey_pause_var, bg="#0f3460",
                fg=self.colors["text"], relief="flat", width=10).grid(row=2, column=1, padx=5)
        
        tk.Label(hotkey_frame, text="Gravar:", bg=self.colors["bg_light"],
                fg=self.colors["text"]).grid(row=3, column=0, sticky="w", pady=5, padx=5)
        hotkey_record_var = tk.StringVar(value=self.bot.config.data["hotkey_record"])
        tk.Entry(hotkey_frame, textvariable=hotkey_record_var, bg="#0f3460",
                fg=self.colors["text"], relief="flat", width=10).grid(row=3, column=1, padx=5)
        
        tk.Label(config_frame, text="Exemplo: f1, f2, ctrl+shift+f5, etc.",
                bg=self.colors["bg_light"], fg=self.colors["text_dim"],
                font=("Arial", 8)).pack(pady=5)
        
        def save_settings():
            try:
                # Remove hotkeys antigas
                keyboard.unhook_all()
                
                # Atualiza configurações
                self.bot.config.data["hotkey_start"] = hotkey_start_var.get()
                self.bot.config.data["hotkey_stop"] = hotkey_stop_var.get()
                self.bot.config.data["hotkey_pause"] = hotkey_pause_var.get()
                self.bot.config.data["hotkey_record"] = hotkey_record_var.get()
                self.bot.config.save()
                
                # Reconfigura hotkeys
                self.setup_hotkeys()
                
                messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar configurações: {e}")
        
        # Botões
        btn_frame = tk.Frame(dialog, bg=self.colors["bg"])
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="💾 Salvar", command=save_settings,
                 bg=self.colors["success"], fg="#000", font=("Arial", 10, "bold"),
                 padx=30, pady=8, relief="flat", cursor="hand2").pack(side="left", padx=5)
        
        tk.Button(btn_frame, text="✗ Cancelar", command=dialog.destroy,
                 bg=self.colors["danger"], fg="#fff", font=("Arial", 10, "bold"),
                 padx=30, pady=8, relief="flat", cursor="hand2").pack(side="left", padx=5)
    
    def check_updates(self):
        """Verifica se há atualizações disponíveis"""
        self.add_log("🔍 Verificando atualizações...", "INFO")
        self.btn_update.config(state="disabled", text="🔄 VERIFICANDO...")
        
        def check_thread():
            has_update, version, changelog = check_for_updates()
            
            def update_ui():
                self.btn_update.config(state="normal", text="🔄 ATUALIZAR")
                
                if has_update:
                    self.add_log(f"✨ Nova versão disponível: v{version}", "SUCCESS")
                    self.show_update_dialog(version, changelog)
                else:
                    self.add_log(f"✅ Você já está usando a versão mais recente (v{VERSION})", "SUCCESS")
                    messagebox.showinfo("Atualização", f"Você já está usando a versão mais recente!\n\nVersão atual: v{VERSION}")
            
            self.root.after(0, update_ui)
        
        threading.Thread(target=check_thread, daemon=True).start()
    
    def show_update_dialog(self, new_version, changelog):
        """Mostra diálogo com informações da atualização"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Atualização Disponível")
        dialog.geometry("500x400")
        dialog.configure(bg=self.colors["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        
        self.position_dialog_window(dialog)
        
        tk.Label(dialog, text="🎉 NOVA VERSÃO DISPONÍVEL!", bg=self.colors["bg"],
                fg=self.colors["success"], font=("Arial", 14, "bold")).pack(pady=20)
        
        info_frame = tk.Frame(dialog, bg=self.colors["bg_light"], relief="groove", borderwidth=2)
        info_frame.pack(padx=20, pady=10, fill="both", expand=True)
        
        tk.Label(info_frame, text=f"Versão Atual: v{VERSION}", bg=self.colors["bg_light"],
                fg=self.colors["text"], font=("Arial", 11)).pack(pady=5)
        
        tk.Label(info_frame, text=f"Nova Versão: v{new_version}", bg=self.colors["bg_light"],
                fg=self.colors["success"], font=("Arial", 11, "bold")).pack(pady=5)
        
        tk.Label(info_frame, text="Novidades:", bg=self.colors["bg_light"],
                fg=self.colors["text"], font=("Arial", 10, "bold")).pack(pady=(10, 5))
        
        changelog_text = tk.Text(info_frame, bg="#0f3460", fg=self.colors["text"],
                                relief="flat", height=8, wrap="word")
        changelog_text.pack(padx=10, pady=5, fill="both", expand=True)
        changelog_text.insert("1.0", changelog)
        changelog_text.config(state="disabled")
        
        # Barra de progresso
        self.update_progress = ttk.Progressbar(dialog, mode='determinate', length=400)
        
        def start_update():
            self.update_progress.pack(pady=10)
            btn_download.config(state="disabled", text="⏳ Baixando...")
            btn_cancel.config(state="disabled")
            
            def download_thread():
                def progress_callback(percent):
                    self.root.after(0, lambda: self.update_progress.config(value=percent))
                
                success, result = download_update(progress_callback)
                
                def finish_download():
                    if success:
                        self.add_log("✅ Atualização baixada com sucesso!", "SUCCESS")
                        messagebox.showinfo("Sucesso", "Atualização baixada! O programa será reiniciado.")
                        dialog.destroy()
                        apply_update(result)
                        self.root.quit()
                    else:
                        self.add_log(f"❌ Erro ao baixar atualização: {result}", "ERROR")
                        messagebox.showerror("Erro", f"Erro ao baixar atualização:\n{result}")
                        btn_download.config(state="normal", text="⬇ Baixar e Instalar")
                        btn_cancel.config(state="normal")
                        self.update_progress.pack_forget()
                
                self.root.after(0, finish_download)
            
            threading.Thread(target=download_thread, daemon=True).start()
        
        # Botões
        btn_frame = tk.Frame(dialog, bg=self.colors["bg"])
        btn_frame.pack(pady=20)
        
        btn_download = tk.Button(btn_frame, text="⬇ Baixar e Instalar", command=start_update,
                                bg=self.colors["success"], fg="#000", font=("Arial", 10, "bold"),
                                padx=30, pady=8, relief="flat", cursor="hand2")
        btn_download.pack(side="left", padx=5)
        
        btn_cancel = tk.Button(btn_frame, text="✗ Agora Não", command=dialog.destroy,
                              bg=self.colors["danger"], fg="#fff", font=("Arial", 10, "bold"),
                              padx=30, pady=8, relief="flat", cursor="hand2")
        btn_cancel.pack(side="left", padx=5)
    
    def run(self):
        # Verifica se há arquivo de auto-start
        auto_start_file = "auto_start.json"
        if os.path.exists(auto_start_file):
            try:
                with open(auto_start_file, "r", encoding="utf-8") as f:
                    self.bot.commands = json.load(f)
                self.refresh_command_list()
                self.add_log("📂 Comandos auto-carregados de auto_start.json", "SUCCESS")
                self.add_log("▶️ Iniciando execução automática...", "INFO")
                # Inicia execução após um pequeno delay
                self.root.after(1000, self.start_execution)
                self.root.mainloop()
                return
            except Exception as e:
                self.add_log(f"⚠️ Erro ao carregar auto_start.json: {e}", "WARN")
        
        self.add_log("🚀 GDMmacrobot v1 iniciado!", "SUCCESS")
        self.add_log("📋 Adicione comandos e pressione INICIAR", "INFO")
        self.root.mainloop()

# ==================== MAIN ====================
if __name__ == "__main__":
    app = ModernUI()
    app.run()
