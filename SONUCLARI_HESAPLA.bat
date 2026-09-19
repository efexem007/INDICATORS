@echo off
title CANLI TAKIP - SONUC DEGERLENDIRME (forward return / MFE / MAE)
chcp 65001 >nul
cd /d "%~dp0"
echo Tum takip calismalarinin eksik sonuclari tamamlanip gunluk tablolari uretiliyor.
echo Takip SURERKEN de calistirilabilir; son ~66 dakikayi takip programi kendisi yazar.
echo Belirli bir calisma icin: python live_tracker.py --outcomes run_YYYYMMDD_HHMMSS
python live_tracker.py --outcomes all
pause
