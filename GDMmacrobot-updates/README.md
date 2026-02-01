# 🔄 Sistema de Atualização Automática - GDMmacrobot

## 📋 Como Configurar

### 1️⃣ Criar Repositório no GitHub

1. Crie um novo repositório no GitHub (pode ser público ou privado)
2. Nome sugerido: `GDMmacrobot-updates`

### 2️⃣ Configurar URLs no Código

Abra o arquivo `GDMmacrobot.py` e altere estas linhas (próximo ao topo do arquivo):

```python
UPDATE_URL = "https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/version.json"
DOWNLOAD_URL = "https://github.com/SEU_USUARIO/SEU_REPO/releases/latest/download/GDMmacrobot.exe"
```

**Substitua:**
- `SEU_USUARIO` pelo seu nome de usuário do GitHub
- `SEU_REPO` pelo nome do repositório criado

**Exemplo:**
```python
UPDATE_URL = "https://raw.githubusercontent.com/joao123/GDMmacrobot-updates/main/version.json"
DOWNLOAD_URL = "https://github.com/joao123/GDMmacrobot-updates/releases/latest/download/GDMmacrobot.exe"
```

### 3️⃣ Fazer Upload do version.json

1. Faça upload do arquivo `version.json` para a raiz do seu repositório
2. O arquivo deve estar na branch `main`

### 4️⃣ Criar Release no GitHub

Quando tiver uma nova versão:

1. Vá em "Releases" no seu repositório
2. Clique em "Create a new release"
3. Tag version: `v1.0.1` (sempre incrementando)
4. Release title: `Versão 1.0.1`
5. Faça upload do arquivo `GDMmacrobot.exe` na seção "Attach binaries"
6. **IMPORTANTE:** O arquivo deve se chamar exatamente `GDMmacrobot.exe`
7. Clique em "Publish release"

### 5️⃣ Atualizar version.json

Sempre que fizer uma release, atualize o `version.json` no repositório:

```json
{
    "version": "1.0.1",
    "changelog": "✨ Novidades:\n- Nova funcionalidade X\n- Melhorias em Y\n\n🐛 Correções:\n- Bug Z corrigido"
}
```

## 🎯 Como Funciona

1. **Usuário clica em "🔄 ATUALIZAR"**
2. O programa verifica o `version.json` no GitHub
3. Se houver versão mais nova, mostra diálogo com changelog
4. Usuário pode baixar e instalar
5. Programa baixa o novo `.exe` do GitHub Releases
6. Faz backup do executável atual
7. Substitui pelo novo
8. Reinicia automaticamente

## 🔐 Repositório Privado

Se usar repositório privado, você precisará:

1. Criar um Personal Access Token no GitHub
2. Modificar o código para incluir autenticação:

```python
import urllib.request

req = urllib.request.Request(UPDATE_URL)
req.add_header('Authorization', f'token SEU_TOKEN_AQUI')
```

## 📝 Versionamento

Use versionamento semântico (SemVer):
- `1.0.0` → Versão inicial
- `1.0.1` → Correção de bugs
- `1.1.0` → Nova funcionalidade
- `2.0.0` → Mudanças grandes/breaking changes

## ⚠️ Importante

- O arquivo `.exe` no release **DEVE** se chamar `GDMmacrobot.exe`
- Sempre incremente a versão no `version.json`
- Teste a atualização antes de distribuir
- Mantenha um backup das versões antigas

## 🧪 Testar Localmente

Para testar sem GitHub:

1. Coloque o `version.json` em um servidor local
2. Altere as URLs para apontar para localhost
3. Incremente a versão no `version.json`
4. Teste o botão de atualização

## 🚀 Distribuição

Quando enviar para alguém:
1. Compile o programa com PyInstaller
2. A pessoa receberá o `.exe`
3. Ela poderá clicar em "Atualizar" dentro do programa
4. O programa baixará automaticamente do GitHub

## 📧 Suporte

Se tiver problemas, verifique:
- URLs estão corretas
- `version.json` está acessível
- Release foi publicada corretamente
- Nome do arquivo é `GDMmacrobot.exe`
