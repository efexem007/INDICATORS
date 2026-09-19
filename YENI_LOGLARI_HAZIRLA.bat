@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/2] Yalniz en yeni runin eklenen kayitlari ve bekleyen sonuclarin guncellemeleri ayriliyor.
python research_updates.py
if errorlevel 1 (
  echo Kaynak kontrolu basarisiz. Eski veri tekrar analiz edilmedi; defter de guncellenmedi.
  pause
  exit /b 1
)
echo.
echo [2/2] Hipotez ve eksik defteri en yeni lab ciktisina gore guncelleniyor.
echo Yeni tur acilmasi icin o run hypothesis_lab.py ile yeniden degerlendirilmis olmali.
echo Ayni run ayni menu ve ayni replay ile ise NO_NEW_EVIDENCE yazar; bu normaldir.
python research_ledger.py
if errorlevel 1 echo Defter guncellenemedi; onceki tur oldugu gibi duruyor.
echo.
echo Defter: ARASTIRMA\DEFTER\HIPOTEZ_DEFTERI.md ve ARASTIRMA\DEFTER\EKSIKLER.md
pause
