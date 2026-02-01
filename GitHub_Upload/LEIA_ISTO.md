# 📦 Pasta GitHub_Upload - Pronta para Upload!

## ✅ Arquivos Incluídos

Esta pasta contém TODOS os arquivos necessários para o seu repositório GitHub:

### 📄 Arquivos Principais
- ✅ **GDMmacrobot.py** - Código-fonte do programa
- ✅ **version.json** - Controle de versão para atualizações
- ✅ **config.json** - Configurações padrão

### 🎨 Recursos Visuais
- ✅ **logo.png** - Logo do programa
- ✅ **icon.png** - Ícone PNG
- ✅ **icon.ico** - Ícone ICO

### 📚 Documentação
- ✅ **README.md** - Página principal do repositório
- ✅ **.gitignore** - Arquivos que o Git deve ignorar

### 📁 Pastas
- ✅ **targets/** - Pasta de alvos do bot

---

## 🚀 Como Usar

### Método 1: Upload Direto no GitHub (Mais Fácil)

1. Acesse: https://github.com/new
2. Crie um novo repositório (ex: `gdm-macrobot`)
3. Depois de criado, clique em **"uploading an existing file"**
4. **Arraste TODA a pasta GitHub_Upload** para a janela
5. Commit message: `🎉 Commit inicial`
6. Clique em **"Commit changes"**

### Método 2: Via Git (Linha de Comando)

```powershell
cd "C:\Users\willi\Documents\SuperBot\GitHub_Upload"
git init
git add .
git commit -m "🎉 Commit inicial"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
git push -u origin main
```

---

## ⚠️ ANTES DE FAZER UPLOAD

**IMPORTANTE:** Atualize as URLs no arquivo `GDMmacrobot.py`:

Abra `GitHub_Upload\GDMmacrobot.py` e procure por:
```python
UPDATE_URL = "https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/version.json"
DOWNLOAD_URL = "https://github.com/SEU_USUARIO/SEU_REPO/releases/latest/download/GDMmacrobot.exe"
```

Substitua:
- `SEU_USUARIO` → seu nome de usuário do GitHub
- `SEU_REPO` → nome do repositório que vai criar

**Exemplo:**
```python
UPDATE_URL = "https://raw.githubusercontent.com/joaosilva/gdm-macrobot/main/version.json"
DOWNLOAD_URL = "https://github.com/joaosilva/gdm-macrobot/releases/latest/download/GDMmacrobot.exe"
```

---

## 📋 Próximos Passos

### 1. Atualizar URLs ⚠️
- Edite `GDMmacrobot.py` com suas URLs

### 2. Criar Repositório 🌐
- Vá em https://github.com/new
- Nome: `gdm-macrobot` (ou outro)
- Público ou Privado
- Não marque "Add README"

### 3. Fazer Upload 📤
- Arraste os arquivos desta pasta
- Faça commit

### 4. Compilar Executável 🔨
```powershell
cd "C:\Users\willi\Documents\SuperBot"
pip install pyinstaller
pyinstaller --onefile --windowed --name="GDMmacrobot" --icon="logo.png" GDMmacrobot.py
```
Resultado em: `dist\GDMmacrobot.exe`

### 5. Criar Release 🚀
- No GitHub: Releases → Create new release
- Tag: `v1.0.0`
- Upload: `dist\GDMmacrobot.exe`
- Publicar!

---

## ✅ Checklist

Antes de distribuir:

- [ ] URLs atualizadas no GDMmacrobot.py
- [ ] Repositório criado no GitHub
- [ ] Arquivos desta pasta enviados
- [ ] Executável compilado
- [ ] Release criada com .exe
- [ ] Botão de atualização testado

---

## 📞 Ajuda

Siga o guia completo em: `COMO_USAR_GITHUB.md`

---

**🎉 Tudo pronto para o GitHub!**
