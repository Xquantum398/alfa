# 📺 tvproxy

## 🚀 M3U8 Proxy Dockerizzato

Un server proxy leggero basato su **Flask** e **Requests**, progettato per:

- 📥 Scaricare e modificare flussi **.m3u / .m3u8**
- 🔁 Proxare i segmenti `.ts`, mantenendo header personalizzati
- 🚫 Superare restrizioni come **Referer**, **User-Agent**, ecc.
- 🐳 Essere facilmente **dockerizzabile** su qualsiasi macchina o server

---

## ☁️ Deploy su Render

1. Vai su **Projects → Deploy a Web Service → Public Git Repo**
2. Inserisci il repo: `https://github.com/nzo66/tvproxy` → **Connect**
3. Dai un nome a piacere
4. Imposta **Instance Type** su `Free`
5. Clicca su **Deploy Web Service**

---

## 🤗 Deploy su HuggingFace

1. Crea un nuovo **Space**
2. Scegli un nome qualsiasi e imposta **Docker** come tipo
3. Lascia **Public** e crea lo Space
4. Vai in alto a destra → `⋮` → **Files** → carica tutti i file della repo
5. Infine vai su `⋮` → **Embed this Space** per ottenere il **Direct URL**

---

## 🐳 Docker (Locale o Server)

### ✅ Costruzione e Avvio

```bash
git clone https://github.com/nzo66/tvproxy.git
cd tvproxy
docker build -t tvproxy .
docker run -d -p 7860:7860 --name tvproxy tvproxy
```

---

## 🐍 Avvio con Python (Locale)

### ✅ Setup e Avvio

```bash
# Clona il repository
git clone https://github.com/nzo66/tvproxy.git
cd tvproxy

# Installa le dipendenze
pip install -r requirements.txt

# Avvia il server
gunicorn app:app -w 4 -b 0.0.0.0:7860
```

---

## 🛠️ Gestione Docker

- 📄 Logs: `docker logs -f tvproxy`
- ⛔ Stop: `docker stop tvproxy`
- 🔄 Start: `docker start tvproxy`
- 🧹 Rimozione: `docker rm -f tvproxy`

---

## 🔗 Utilizzo del Proxy

```txt
http://<server-ip>:7860/proxy/m3u?url=<URL_M3U8>
```

> ⚠️ Non proxare l'intera lista! Inserisci il proxy **prima di ogni URL m3u8**:

```
http://<server-ip>:7860/proxy/m3u?url=https://example.com/stream.m3u8
```

### 🎯 Headers Personalizzati (opzionale)

```txt
&h_user-agent=Mozilla/5.0...&h_referer=https://ilovetoplay.xyz/&h_origin=https://ilovetoplay.xyz
```

---

## ✅ Caratteristiche

- 📁 Supporta **.m3u** e **.m3u8** automaticamente
- 🧾 Inoltra gli **HTTP Headers** necessari (Auth, Referer, etc.)
- 🔓 Supera restrizioni geografiche o di accesso
- 🖥️ Compatibile con **qualsiasi player IPTV**
- 🐳 Totalmente dockerizzato, pronto per il deploy
- 🐍 Avviabile anche direttamente con **Python**

---

## 🎉 Fine!

> Ora puoi guardare flussi M3U8 ovunque, senza restrizioni!  
> Enjoy the Stream 🚀