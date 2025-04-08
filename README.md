# 🎵 OtoRadio for ETS2
> ETS2'yi açtığın anda, otomatik olarak müziklerini senkronize eden YouTube playlist indirici!

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Status](https://img.shields.io/badge/Status-Active-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20Only-lightgrey)

## 🚀 Özellikler

- ✅ YouTube playlist'ten mp3 formatında şarkı indirir.
- 🎮 ETS2 (Euro Truck Simulator 2) çalıştığında otomatik senkron başlatır.
- 🧠 ID3 etiketleri (şarkı adı, sanatçı) otomatik eklenir.
- 🖥️ GUI üzerinden senkron başlatma, log görüntüleme ve şarkı yönetimi yapılabilir.
- 📂 ETS2'nin `Documents` altındaki `music` klasörünü otomatik kullanır.
- 🔊 Kalite seçimi: 128 / 192 / 320 kbps
- 🛑 Tray ikonu ile arka planda sessiz çalışır.
- ⚙️ Otomatik Windows başlangıcına eklenir.

## 📸 Ekran Görüntüsü

> ~Eklenecek

## 🛠️ Kurulum

1. Bu repoyu klonla:

```bash
git clone https://github.com/kullaniciadi/OtoRadio-For-ETS2.git
cd OtoRadio-For-ETS2
```

2. Sanal ortam oluştur:

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Gereken paketleri kur:

```bash
pip install -r requirements.txt
```

4. Uygulamayı başlat:

```bash
python main.py
```

## ⚙️ Kullanım

- GUI açıldığında playlist linkini yapıştır.
- Kaliteyi seç.
- “Senkronizasyonu Başlat”a tıkla.
- ETS2’yi açtığında artık yeni müziklerin otomatik eklenecek.

## 💬 SSS

**S: Bu uygulama Linux’ta çalışır mı?**  
Hayır, şu an yalnızca Windows ortamında çalışır çünkü `pystray` ve `win32com` kullanıyor.

**S: ETS2 açılmadan da indirir mi?**  
Evet, "ETS2 açık olmasa da çalıştır" kutusunu işaretlersen senkronizasyon ETS2’ye bağlı kalmaz.

**S: Şarkılar nereye indiriliyor?**  
Direkt olarak ETS2'nin `music` klasörüne:  
`C:\Users\KULLANICI\Documents\Euro Truck Simulator 2\music`

## 📁 Proje Yapısı

```txt
OtoRadio-For-ETS2/
├── main.py              → Ana uygulama kodu
├── config.json          → Kullanıcı ayarları (playlist, kaynak)
├── error.log            → Hata kayıtları burada tutulur
├── requirements.txt     → Gereken pip modülleri listesi
├── README.md            → GitHub açıklama dosyası
├── .gitignore           → Gereksiz dosyaları git’e ekleme
└── docs/                → (isteğe bağlı) ekran görüntüleri
```

## 📦 requirements.txt

```txt
yt-dlp
mutagen
pystray
plyer
pillow
psutil
```

## 👨‍💻 Geliştirici

- **Faruk-Kara**
- Discord: t.o.f.k.

## 📄 Lisans

MIT Lisansı altında açık kaynak.
