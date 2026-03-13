/*
 * controladores_io.cpp
 * Compilar MinGW:
 *   g++ controladores_io.cpp -o controladores_io.exe
 *       -luser32 -lgdi32 -lshell32 -lole32 -loleaut32 -lwbemuuid -luuid -std=c++17
 */

#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
#include <map>
#include <deque>
#include <cmath>
#include <ctime>
#include <algorithm>
#include <windows.h>
#include <wbemidl.h>
#include <oleauto.h>
#include <psapi.h>
#include <tlhelp32.h>

using namespace std;

#pragma comment(lib, "wbemuuid.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "oleaut32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "psapi.lib")

const string RST  = "\033[0m";
const string BOLD = "\033[1m";
const string DIM  = "\033[2m";
const string WHT  = "\033[97m";
const string GRN  = "\033[32m";
const string RED  = "\033[31m";
const string GRY  = "\033[90m";
const string YEL  = "\033[33m";
const string CYN  = "\033[36m";
const string MGN  = "\033[35m";
const string BLU  = "\033[34m";

void enableColors() {
    HANDLE h = GetStdHandle(STD_OUTPUT_HANDLE);
    DWORD m = 0; GetConsoleMode(h, &m);
    SetConsoleMode(h, m | ENABLE_VIRTUAL_TERMINAL_PROCESSING);
}

void sep(char c = '-', int n = 80) {
    cout << GRY << string(n, c) << RST << "\n";
}

string hx(unsigned long long v, int nib = 2) {
    ostringstream s;
    s << "0x" << uppercase << hex << setw(nib) << setfill('0') << v;
    return s.str();
}
string hxb(bool v) { return v ? "0x01" : "0x00"; }

static string pad(const string& s, int w) {
    string r = s;
    if((int)r.size() > w) r = r.substr(0,w-2)+"..";
    while ((int)r.size() < w) r += ' ';
    return r;
}

void row(const string& campo, const string& hexval,
         const string& val, bool alert = false) {
    cout << "  " << pad(campo, 30)
         << BOLD << WHT << pad(hexval, 14) << RST;
    if (alert) cout << RED; else cout << DIM;
    cout << val << RST << "\n";
}

void header(const string& sec) {
    cout << "\n" << BOLD << CYN << "  \u250c\u2500 " << sec << RST << "\n";
    sep();
    cout << GRY << "  "
         << pad("CAMPO", 30) << pad("HEX", 14) << "VALOR" << RST << "\n";
    sep();
}

struct IRQEvento { string irq; string vec; string evento; bool activa; };

void seccionIRQ(const string& titulo, const vector<IRQEvento>& ev) {
    cout << "\n" << BOLD << WHT << "  " << titulo << RST << "\n";
    sep();
    cout << GRY << "  "
         << pad("IRQ", 8) << pad("VECTOR", 10) << pad("HEX", 8)
         << pad("EVENTO", 36) << "ESTADO" << RST << "\n";
    sep();
    for (auto& e : ev) {
        string hexA = e.activa ? "0x01" : "0x00";
        string est  = e.activa ? GRN + "ACTIVA"   + RST
                               : RED + "INACTIVA" + RST;
        cout << "  "
             << pad(e.irq, 8) << pad(e.vec, 10)
             << BOLD << WHT << pad(hexA, 8) << RST
             << pad(e.evento, 36) << est << "\n";
    }
}

void seccionDMA(const string& titulo,
                const string& canal, const string& modo,
                const string& dirBase,
                unsigned long long bytesTotal,
                unsigned long long bytesXfer,
                bool activo, bool error,
                const string& nota) {
    cout << "\n" << BOLD << WHT << "  " << titulo << RST << "\n";
    sep();
    cout << GRY << "  "
         << pad("CAMPO", 30) << pad("HEX", 14) << "VALOR" << RST << "\n";
    sep();
    if (!nota.empty()) {
        row("Uso de DMA", "0x00", "NO APLICA  --  " + nota);
        return;
    }
    row("Canal DMA",             canal,  "");
    row("Modo de transferencia", modo,   "");
    row("Dir. base destino",     dirBase,"");
    row("Bytes a transferir",    hx(bytesTotal,8), to_string(bytesTotal)+" bytes");
    row("Bytes transferidos",    hx(bytesXfer, 8), to_string(bytesXfer) +" bytes");
    row("Transferencia activa",  hxb(activo), activo?GRN+string("SI")+RST:string("NO"));
    row("Error DMA",             hxb(error),  error ?RED+string("SI")+RST:string("NO"), error);
}

// ── WMI helper ────────────────────────────────────────────────
struct WMI {
    IWbemLocator*  pLoc = nullptr;
    IWbemServices* pSvc = nullptr;
    bool ok = false;
    WMI() {
        CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        CoInitializeSecurity(nullptr,-1,nullptr,nullptr,
            RPC_C_AUTHN_LEVEL_DEFAULT,RPC_C_IMP_LEVEL_IMPERSONATE,
            nullptr,EOAC_NONE,nullptr);
        if (FAILED(CoCreateInstance(CLSID_WbemLocator,nullptr,
            CLSCTX_INPROC_SERVER,IID_IWbemLocator,(void**)&pLoc))) return;
        BSTR ns=SysAllocString(L"ROOT\\CIMV2");
        HRESULT hr=pLoc->ConnectServer(ns,nullptr,nullptr,
            nullptr,0,nullptr,nullptr,&pSvc);
        SysFreeString(ns);
        if (FAILED(hr)){pLoc->Release();pLoc=nullptr;return;}
        CoSetProxyBlanket(pSvc,RPC_C_AUTHN_WINNT,RPC_C_AUTHZ_NONE,nullptr,
            RPC_C_AUTHN_LEVEL_CALL,RPC_C_IMP_LEVEL_IMPERSONATE,nullptr,EOAC_NONE);
        ok=true;
    }
    ~WMI(){
        if(pSvc)pSvc->Release();
        if(pLoc)pLoc->Release();
        CoUninitialize();
    }
    IEnumWbemClassObject* query(const wchar_t* q){
        if(!ok)return nullptr;
        IEnumWbemClassObject* e=nullptr;
        BSTR wql=SysAllocString(L"WQL");
        BSTR bq =SysAllocString(q);
        pSvc->ExecQuery(wql,bq,
            WBEM_FLAG_FORWARD_ONLY|WBEM_FLAG_RETURN_IMMEDIATELY,nullptr,&e);
        SysFreeString(wql); SysFreeString(bq);
        return e;
    }
    static string str(IWbemClassObject* o,const wchar_t* f){
        VARIANT v; VariantInit(&v); string r="N/A";
        if(SUCCEEDED(o->Get(f,0,&v,nullptr,nullptr))){
            if(v.vt==VT_BSTR&&v.bstrVal){
                int sz=WideCharToMultiByte(CP_UTF8,0,v.bstrVal,-1,nullptr,0,nullptr,nullptr);
                if(sz>1){string s(sz-1,0);
                    WideCharToMultiByte(CP_UTF8,0,v.bstrVal,-1,&s[0],sz,nullptr,nullptr);
                    r=s;}
            }
        }
        VariantClear(&v); return r;
    }
    static unsigned long long ull(IWbemClassObject* o,const wchar_t* f){
        VARIANT v; VariantInit(&v); unsigned long long r=0;
        if(SUCCEEDED(o->Get(f,0,&v,nullptr,nullptr))){
            if     (v.vt==VT_BSTR&&v.bstrVal) r=_wcstoui64(v.bstrVal,nullptr,10);
            else if(v.vt==VT_I4||v.vt==VT_UI4) r=v.uintVal;
            else if(v.vt==VT_I8||v.vt==VT_UI8) r=v.ullVal;
        }
        VariantClear(&v); return r;
    }
};

// ══════════════════════════════════════════════════════════════
//  MOUSE
// ══════════════════════════════════════════════════════════════
// ── Hook WH_MOUSE_LL en thread dedicado ─────────────────────────────
// El hook necesita su propio message loop continuo.
// Si el thread que instalo el hook tarda >300ms sin procesar mensajes,
// Windows lo desinstala automaticamente causando lag.
static volatile LONG g_scrollAcum = 0;
static HHOOK         g_hHook       = NULL;

LRESULT CALLBACK MouseLLProc(int nCode, WPARAM wParam, LPARAM lParam) {
    if(nCode == HC_ACTION && wParam == WM_MOUSEWHEEL) {
        MSLLHOOKSTRUCT* ms = (MSLLHOOKSTRUCT*)lParam;
        short delta = (short)HIWORD(ms->mouseData);
        InterlockedAdd(&g_scrollAcum, (LONG)delta);
    }
    return CallNextHookEx(g_hHook, nCode, wParam, lParam);
}

// Thread que solo instala el hook y bombea mensajes -- nunca duerme
DWORD WINAPI hookThread(LPVOID) {
    g_hHook = SetWindowsHookExA(WH_MOUSE_LL, MouseLLProc, NULL, 0);
    MSG msg;
    while(GetMessage(&msg, NULL, 0, 0)) {   // bloquea hasta haber mensaje
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    if(g_hHook) UnhookWindowsHookEx(g_hHook);
    return 0;
}

void runMouse() {
    SetConsoleTitleA("MOUSE -- Registros del controlador");
    SetConsoleOutputCP(65001);
    enableColors();

    // Lanzar thread del hook y esperar a que instale el hook
    HANDLE hT = CreateThread(NULL, 0, hookThread, NULL, 0, NULL);
    Sleep(50); // dar tiempo al thread para instalar el hook

    POINT prev; GetCursorPos(&prev);
    bool izqPrev=false, derPrev=false, medPrev=false;
    int  sample=0;

    while (true) {
        Sleep(150);

        POINT cur; GetCursorPos(&cur);
        int dx=cur.x-prev.x;
        int dy=cur.y-prev.y;

        bool izq=(GetAsyncKeyState(VK_LBUTTON)&0x8000)!=0;
        bool der=(GetAsyncKeyState(VK_RBUTTON)&0x8000)!=0;
        bool med=(GetAsyncKeyState(VK_MBUTTON)&0x8000)!=0;

        bool clicIzq=izq&&!izqPrev;
        bool clicDer=der&&!derPrev;
        bool clicMed=med&&!medPrev;

        // Leer y resetear el acumulador de scroll atomicamente
        int scroll = (int)InterlockedExchange(&g_scrollAcum, 0);

        bool dataReady=(dx!=0||dy!=0||izq||der||med||scroll!=0);
        bool ocupado=dataReady;

        sample++;
        unsigned char b1=0x08;
        if(izq)  b1|=0x01;
        if(der)  b1|=0x02;
        if(med)  b1|=0x04;
        if(dx<0) b1|=0x10;
        if(dy>0) b1|=0x20;
        unsigned char b2=(unsigned char)(dx&0xFF);
        unsigned char b3=(unsigned char)((-dy)&0xFF);

        string dir="quieto";
        if(abs(dx)>0||abs(dy)>0)
            dir=(abs(dx)>=abs(dy))?(dx>0?"derecha":"izquierda"):(dy>0?"abajo":"arriba");

        // scrollClicks: positivo = arriba, negativo = abajo
        int scrollClicks = scroll / 120;
        string scrollStr="sin movimiento";
        if(scrollClicks > 0) scrollStr=GRN+"ARRIBA  (+"+to_string( scrollClicks)+" click)"+RST;
        if(scrollClicks < 0) scrollStr=RED+"ABAJO   ("+to_string(-scrollClicks)+" click)"+RST;

        if(!dataReady){ prev=cur; izqPrev=izq; derPrev=der; medPrev=med; continue; }
        system("cls");
        sep('=',80);
        cout<<BOLD<<WHT<<"  MOUSE  PS/2  IRQ 12  (0x74)"
            <<"   muestra #"<<sample<<RST<<"\n";
        sep('=',80);

        header("DATOS");
        row("X  desplaz. horizontal",hx(b2),to_string(dx)+" px   "+dir);
        row("Y  desplaz. vertical",  hx(b3),to_string(dy)+" px");
        row("Rueda  scroll", scrollClicks!=0?hx((unsigned char)abs(scrollClicks)):"0x00", scrollStr);
        row("Boton izquierdo",hxb(izq),izq?GRN+"PRESIONADO"+RST:string("suelto"));
        row("Boton derecho",  hxb(der),der?GRN+"PRESIONADO"+RST:string("suelto"));
        row("Boton central",  hxb(med),med?GRN+"PRESIONADO"+RST:string("suelto"));
        cout<<"  "<<GRY<<"Paquete PS/2: "
            <<BOLD<<WHT<<"B1="<<hx(b1)<<"  B2="<<hx(b2)<<"  B3="<<hx(b3)
            <<RST<<GRY<<"  [flags | deltaX | deltaY]"<<RST<<"\n";

        header("ESTADO");
        row("Data ready",        hxb(dataReady),dataReady?GRN+"SI"+RST:string("NO"));
        row("Buffer lleno",      "0x00","libre");
        row("Error comunicacion","N/A", "no accesible sin driver");
        row("Ocupado",           hxb(ocupado),ocupado?GRN+"procesando"+RST:string("inactivo"));

        header("COMANDO / CONTROL");
        row("Activar mouse",         "0xA8","Enable auxiliary device  (KBC)");
        row("Habilitar interrupcion","0x02","bit 1 CCB  ->  IRQ 12 ON");
        row("Resetear",              "0xFF","Reset + self-test  (no ejecutado)");
        row("Sensibilidad DPI",      "0x320","800 DPI  (media  estandar PS/2)");

        seccionIRQ("INTERRUPCIONES  --  IRQ 12  (vector 0x74)",{
            {"IRQ 12","0x74","Movimiento detectado",         dataReady&&(dx!=0||dy!=0)},
            {"IRQ 12","0x74","Clic boton izquierdo (flanco)",clicIzq},
            {"IRQ 12","0x74","Clic boton derecho   (flanco)",clicDer},
            {"IRQ 12","0x74","Clic boton central   (flanco)",clicMed},
            {"IRQ 12","0x74","Scroll rueda arriba",          scrollClicks>0},
            {"IRQ 12","0x74","Scroll rueda abajo",           scrollClicks<0},
            {"IRQ 12","0x74","Boton izq. mantenido",         izq},
            {"IRQ 12","0x74","Boton der. mantenido",         der},
            {"IRQ 12","0x74","Paquete PS/2 completo  (3B)",  dataReady},
            {"IRQ 12","0x74","Error de comunicacion",        false},
        });

        seccionDMA("DMA  --  ACCESO DIRECTO A MEMORIA",
            "","","",0,0,false,false,
            "3 bytes por evento via IRQ 12. Volumen minimo, sin DMA.");

        sep('=',80);
        prev=cur; izqPrev=izq; derPrev=der; medPrev=med;
    }
}

// ══════════════════════════════════════════════════════════════
//  TECLADO
// ══════════════════════════════════════════════════════════════
struct EstadoTecla { int veces=0; ULONGLONG tUltimo=0; };

string nombreVK(int vk) {
    if(vk>='A'&&vk<='Z')          return string(1,(char)vk);
    if(vk>='0'&&vk<='9')          return string(1,(char)vk);
    if(vk>=VK_F1&&vk<=VK_F12)     return "F"+to_string(vk-VK_F1+1);
    switch(vk){
        case VK_SPACE:   return "ESPACIO";
        case VK_RETURN:  return "ENTER";
        case VK_ESCAPE:  return "ESC";
        case VK_BACK:    return "RETROCESO";
        case VK_TAB:     return "TAB";
        case VK_SHIFT:   return "SHIFT";
        case VK_CONTROL: return "CTRL";
        case VK_MENU:    return "ALT";
        case VK_LEFT:    return "FLECHA IZQ";
        case VK_RIGHT:   return "FLECHA DER";
        case VK_UP:      return "FLECHA ARR";
        case VK_DOWN:    return "FLECHA ABA";
        case VK_DELETE:  return "DELETE";
        case VK_INSERT:  return "INSERT";
        case VK_HOME:    return "HOME";
        case VK_END:     return "END";
        case VK_PRIOR:   return "PAGE UP";
        case VK_NEXT:    return "PAGE DOWN";
        default:         return "VK("+to_string(vk)+")";
    }
}

void runTeclado() {
    SetConsoleTitleA("TECLADO -- Registros del controlador");
    SetConsoleOutputCP(65001);
    enableColors();

    map<int,EstadoTecla> estado;
    int ultimoVK=-1, conteoUltimo=0;
    int    cur_vk=0,cur_sc=0,cur_release=0;
    bool   cur_mayus=false,cur_ctrl=false,cur_alt=false,cur_caps=false;
    bool   cur_rep=false,cur_bufLleno=false;
    int    cur_veces=0,cur_intervalo=0,cur_modoNum=0;
    string cur_modoStr="---",cur_ascii=" ";
    bool   hay_evento=false;
    int    sample=0;

    while(true){
        bool hubo_tecla_ciclo=false;
        bool mayus=(GetAsyncKeyState(VK_SHIFT)  &0x8000)!=0;
        bool ctrl =(GetAsyncKeyState(VK_CONTROL)&0x8000)!=0;
        bool alt  =(GetAsyncKeyState(VK_MENU)   &0x8000)!=0;
        bool caps =(GetKeyState(VK_CAPITAL)     &0x0001)!=0;

        for(int vk=8;vk<=255;vk++){
            if(!(GetAsyncKeyState(vk)&0x0001)) continue;
            auto& est=estado[vk];
            ULONGLONG ahora=GetTickCount64();
            int intervalo=(est.tUltimo>0)?(int)(ahora-est.tUltimo):0;
            bool esRep=false;
            if(vk==ultimoVK){conteoUltimo++;if(conteoUltimo>=2)esRep=true;}
            else{ultimoVK=vk;conteoUltimo=1;}
            est.veces++;est.tUltimo=ahora;
            int sc=(int)MapVirtualKey(vk,MAPVK_VK_TO_VSC);
            int release=sc|0x80;
            BYTE ks[256]={};
            GetKeyboardState(ks);
            WCHAR buf[4]={};
            string ascii_str=nombreVK(vk);
            if(ToUnicode(vk,sc,ks,buf,3,0)>0&&buf[0]>=32)
                ascii_str=string(1,(char)buf[0]);
            bool bufLleno=(est.veces>16);
            bool combina=ctrl||alt;
            int  modoNum=esRep?0x01:(combina?0x02:0x00);
            string modoStr=esRep?"REPETICION  x"+to_string(conteoUltimo)
                :combina?"COMBINACION  CTRL/ALT":"NORMAL";
            cur_vk=vk;cur_sc=sc;cur_release=release;
            cur_mayus=mayus;cur_ctrl=ctrl;cur_alt=alt;cur_caps=caps;
            cur_rep=esRep;cur_veces=est.veces;cur_intervalo=intervalo;
            cur_bufLleno=bufLleno;cur_modoNum=modoNum;
            cur_modoStr=modoStr;cur_ascii=ascii_str;
            hay_evento=true;sample++;hubo_tecla_ciclo=true;
        }

        if(hubo_tecla_ciclo){
            system("cls");
            sep('=',80);
            cout<<BOLD<<WHT<<"  TECLADO  PS/2 KBC 8042  IRQ 1  (0x09)"
                <<"   evento #"<<sample<<RST<<"\n";
            sep('=',80);
            if(!hay_evento){
                cout<<DIM<<"\n  Esperando pulsacion de tecla...\n"<<RST;
            } else {
                header("DATOS  (puerto 0x60)");
                row("Scan code  make", hx(cur_sc),     nombreVK(cur_vk));
                row("Scan code  break",hx(cur_release),"make | 0x80  (release)");
                row("Caracter ASCII",  hx((unsigned char)cur_ascii[0]),"\""+cur_ascii+"\"");
                row("SHIFT",    hxb(cur_mayus),cur_mayus?GRN+"ACTIVO"+RST:string("inactivo"));
                row("CTRL",     hxb(cur_ctrl), cur_ctrl ?GRN+"ACTIVO"+RST:string("inactivo"));
                row("ALT",      hxb(cur_alt),  cur_alt  ?GRN+"ACTIVO"+RST:string("inactivo"));
                row("CAPS LOCK",hxb(cur_caps), cur_caps ?GRN+"ACTIVO"+RST:string("inactivo"));
                row("Pulsaciones esta tecla",hx(cur_veces,4),to_string(cur_veces));

                header("ESTADO  (puerto 0x64)");
                row("Listo  (OBF=1)",    "0x01",GRN+"dato disponible"+RST);
                row("Buffer lleno (IBF)",hxb(cur_bufLleno),
                    cur_bufLleno?RED+"SATURADO"+RST:string("libre"));
                row("Tecla disponible",  "0x01",GRN+"SI"+RST);
                row("Error de paridad",  "0x00","no accesible sin driver");

                header("COMANDO / CONTROL  (puerto 0x64)");
                row("Modo de operacion",hx(cur_modoNum),cur_modoStr,cur_rep);
                if(cur_rep&&cur_intervalo>0){
                    ostringstream ss;
                    ss<<fixed<<setprecision(1)<<1000.0/cur_intervalo
                      <<" pulsos/s  ("<<cur_intervalo<<" ms)";
                    row("Velocidad repeticion",hx(cur_intervalo,4),ss.str());
                }
                row("Resetear teclado",   "0xFF","Reset + self-test");
                row("Repeticion de tecla",hxb(cur_rep),cur_rep?GRN+"ACTIVA"+RST:string("inactiva"));
                row("Interrupciones",     "0x01","IRQ 1 habilitada  (CCB bit 0)");
                row("Comando activo",     "0xF4","Enable Scanning");

                seccionIRQ("INTERRUPCIONES  --  IRQ 1  (vector 0x09)",{
                    {"IRQ 1","0x09","Tecla presionada  (make code)",      true},
                    {"IRQ 1","0x09","Tecla liberada    (break code)",     false},
                    {"IRQ 1","0x09","Buffer entrada lleno  (IBF=1)",      cur_bufLleno},
                    {"IRQ 1","0x09","Error de paridad",                   false},
                    {"IRQ 1","0x09","Modificador activo (SH/CT/AL)",cur_mayus||cur_ctrl||cur_alt},
                    {"IRQ 1","0x09","Modo repeticion activo",             cur_rep},
                });

                seccionDMA("DMA  --  ACCESO DIRECTO A MEMORIA",
                    "","","",0,0,false,false,
                    "1 byte por tecla via IRQ 1. Sin DMA.");
            }
            sep('=',80);
        }
        Sleep(20);
    }
}

// ══════════════════════════════════════════════════════════════
//  MONITOR / GPU  (MEJORADO)
// ══════════════════════════════════════════════════════════════

struct InfoVentana {
    HWND   hwnd;
    string titulo;
    string proceso;
    DWORD  pid;
    RECT   rect;
    string estado;
    bool   esVisible;
    bool   esForeground;
    LONG   estilos;
    LONG   estilosEx;
};

static vector<InfoVentana> g_ventanas;
BOOL CALLBACK enumVentanasProc(HWND hwnd, LPARAM) {
    if(!IsWindowVisible(hwnd)) return TRUE;
    char titulo[256]={};
    GetWindowTextA(hwnd, titulo, 255);
    if(strlen(titulo)==0) return TRUE;

    DWORD pid=0;
    GetWindowThreadProcessId(hwnd, &pid);

    string procNom="N/A";
    HANDLE hProc=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);
    if(hProc){
        char path[MAX_PATH]={};
        DWORD sz=MAX_PATH;
        if(QueryFullProcessImageNameA(hProc,0,path,&sz)){
            string p=path;
            size_t pos=p.rfind('\\');
            if(pos!=string::npos) procNom=p.substr(pos+1);
            else procNom=p;
        }
        CloseHandle(hProc);
    }

    RECT rc={};
    GetWindowRect(hwnd,&rc);

    WINDOWPLACEMENT wp={sizeof(wp)};
    GetWindowPlacement(hwnd,&wp);
    string estado="Normal";
    if(wp.showCmd==SW_MAXIMIZE||wp.showCmd==SW_SHOWMAXIMIZED) estado="Maximizada";
    else if(wp.showCmd==SW_MINIMIZE||wp.showCmd==SW_SHOWMINIMIZED||
            wp.showCmd==SW_FORCEMINIMIZE) estado="Minimizada";

    HWND fg=GetForegroundWindow();

    InfoVentana iv;
    iv.hwnd        = hwnd;
    iv.titulo      = titulo;
    iv.proceso     = procNom;
    iv.pid         = pid;
    iv.rect        = rc;
    iv.estado      = estado;
    iv.esVisible   = true;
    iv.esForeground= (hwnd==fg);
    iv.estilos     = GetWindowLong(hwnd,GWL_STYLE);
    iv.estilosEx   = GetWindowLong(hwnd,GWL_EXSTYLE);
    g_ventanas.push_back(iv);
    return TRUE;
}

struct InfoMonitor {
    HMONITOR hmon;
    string   nombre;
    RECT     rcMonitor;
    RECT     rcWork;
    bool     esPrimario;
    int      anchoPx, altoPx;
    int      dpiX, dpiY;
    int      frecHz;
    int      bpp;
    string   dispositivo;
};

static vector<InfoMonitor> g_monitors;
BOOL CALLBACK enumMonitoresProc(HMONITOR hmon, HDC, LPRECT, LPARAM) {
    MONITORINFOEXA mi; mi.cbSize=sizeof(mi);
    GetMonitorInfoA(hmon,(MONITORINFO*)&mi);

    DEVMODEA dm; ZeroMemory(&dm,sizeof dm); dm.dmSize=sizeof dm;
    EnumDisplaySettingsA(mi.szDevice,ENUM_CURRENT_SETTINGS,&dm);

    HDC hdcM=CreateDCA(mi.szDevice,NULL,NULL,NULL);
    int dX=GetDeviceCaps(hdcM,LOGPIXELSX);
    int dY=GetDeviceCaps(hdcM,LOGPIXELSY);
    DeleteDC(hdcM);

    InfoMonitor im;
    im.hmon      = hmon;
    im.nombre    = mi.szDevice;
    im.rcMonitor = mi.rcMonitor;
    im.rcWork    = mi.rcWork;
    im.esPrimario= (mi.dwFlags & MONITORINFOF_PRIMARY)!=0;
    im.anchoPx   = mi.rcMonitor.right - mi.rcMonitor.left;
    im.altoPx    = mi.rcMonitor.bottom - mi.rcMonitor.top;
    im.dpiX      = dX;
    im.dpiY      = dY;
    im.frecHz    = dm.dmDisplayFrequency;
    im.bpp       = dm.dmBitsPerPel;
    im.dispositivo= mi.szDevice;
    g_monitors.push_back(im);
    return TRUE;
}

void runMonitor() {
    SetConsoleTitleA("MONITOR / GPU -- Registros del controlador");
    SetConsoleOutputCP(65001);
    enableColors();

    WMI wmi;
    string gpuNombre="N/A",gpuDriver="N/A",gpuStatus="N/A";
    string gpuArch="N/A",gpuPCI_ID="N/A";
    unsigned long long gpuVRAM=0;
    string gpuLoad="N/A (requiere HWInfo/GPU-Z)";
    string gpuTemp="N/A (requiere HWInfo/GPU-Z)";

    if(wmi.ok){
        auto pE=wmi.query(L"SELECT * FROM Win32_VideoController");
        if(pE){
            IWbemClassObject* pO=nullptr; ULONG ret=0;
            if(SUCCEEDED(pE->Next(WBEM_INFINITE,1,&pO,&ret))&&ret){
                gpuNombre = WMI::str(pO,L"Name");
                gpuDriver = WMI::str(pO,L"DriverVersion");
                gpuStatus = WMI::str(pO,L"Status");
                gpuVRAM   = WMI::ull(pO,L"AdapterRAM");
                gpuArch   = WMI::str(pO,L"VideoProcessor");
                gpuPCI_ID = WMI::str(pO,L"PNPDeviceID");
                pO->Release();
            }
            pE->Release();
        }
        auto pE2=wmi.query(
            L"SELECT * FROM Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine");
        if(pE2){
            IWbemClassObject* pO2=nullptr; ULONG ret2=0;
            if(SUCCEEDED(pE2->Next(WBEM_INFINITE,1,&pO2,&ret2))&&ret2){
                string u=WMI::str(pO2,L"UtilizationPercentage");
                if(u!="N/A") gpuLoad=u+"%";
                pO2->Release();
            }
            pE2->Release();
        }
    }

    int sample=0;
    deque<string> histFG;

    HWND prevFG=NULL; int prevVentCount=0;
    while(true){
        Sleep(500);

        HWND curFG=GetForegroundWindow();
        g_ventanas.clear();
        EnumWindows(enumVentanasProc,0);
        int curVentCount=(int)g_ventanas.size();
        bool hayEvento=(curFG!=prevFG)||(curVentCount!=prevVentCount);
        prevFG=curFG; prevVentCount=curVentCount;
        if(!hayEvento) continue;
        sample++;

        g_monitors.clear();
        EnumDisplayMonitors(NULL,NULL,enumMonitoresProc,0);

        sort(g_ventanas.begin(),g_ventanas.end(),[](const InfoVentana& a,const InfoVentana& b){
            if(a.esForeground!=b.esForeground) return a.esForeground>b.esForeground;
            return a.pid < b.pid;
        });

        HWND fgHwnd=curFG;
        char fgTit[256]={};
        GetWindowTextA(fgHwnd,fgTit,255);
        if(strlen(fgTit)>0){
            string entry=string(fgTit);
            if(histFG.empty()||histFG.back()!=entry){
                histFG.push_back(entry);
                if(histFG.size()>6) histFG.pop_front();
            }
        }

        int resX=GetSystemMetrics(SM_CXSCREEN);
        int resY=GetSystemMetrics(SM_CYSCREEN);
        int mons=GetSystemMetrics(SM_CMONITORS);
        int virtW=GetSystemMetrics(SM_CXVIRTUALSCREEN);
        int virtH=GetSystemMetrics(SM_CYVIRTUALSCREEN);

        DEVMODEW dm; ZeroMemory(&dm,sizeof dm); dm.dmSize=sizeof dm;
        EnumDisplaySettingsW(NULL,ENUM_CURRENT_SETTINGS,&dm);

        POINT cur; GetCursorPos(&cur);
        int bpp=dm.dmBitsPerPel/8; if(bpp==0)bpp=4;
        long long voff=((long long)cur.y*resX+cur.x)*bpp;
        long long fbSz=(long long)resX*resY*bpp;
        int msFrame=(dm.dmDisplayFrequency>0)?1000/dm.dmDisplayFrequency:0;
        unsigned long long bwMB=(unsigned long long)fbSz*dm.dmDisplayFrequency/1024/1024;

        HDC hdc=GetDC(NULL);
        COLORREF col=GetPixel(hdc,cur.x,cur.y);
        ReleaseDC(NULL,hdc);
        int R=GetRValue(col),G=GetGValue(col),B=GetBValue(col);
        unsigned long px=((unsigned long)R<<16)|((unsigned long)G<<8)|B;

        HDC hdcD=GetDC(NULL);
        int dpiX=GetDeviceCaps(hdcD,LOGPIXELSX);
        int dpiY=GetDeviceCaps(hdcD,LOGPIXELSY);
        ReleaseDC(NULL,hdcD);

        DISPLAY_DEVICEW dispDev; dispDev.cb=sizeof(dispDev);
        string adapterName="N/A";
        if(EnumDisplayDevicesW(NULL,0,&dispDev,0)){
            int sz=WideCharToMultiByte(CP_UTF8,0,dispDev.DeviceString,-1,nullptr,0,nullptr,nullptr);
            if(sz>1){adapterName.resize(sz-1);
                WideCharToMultiByte(CP_UTF8,0,dispDev.DeviceString,-1,
                    &adapterName[0],sz,nullptr,nullptr);}
        }

        system("cls");
        sep('=',80);
        cout<<BOLD<<WHT<<"  MONITOR / GPU  PCIe  IRQ 11  (0x73)"
            <<"   muestra #"<<sample<<RST<<"\n";
        sep('=',80);

        header("GPU  --  ADAPTADOR  (Win32_VideoController)");
        row("Nombre GPU",         "0x--",gpuNombre);
        row("Procesador de video","0x--",gpuArch);
        row("Driver version",     "0x--",gpuDriver);
        row("Estado",             "0x--",gpuStatus);
        {
            ostringstream vv;
            if(gpuVRAM>0) vv<<gpuVRAM/1024/1024<<" MB  ("
                <<fixed<<setprecision(2)<<gpuVRAM/1073741824.0<<" GB)";
            else vv<<"N/A";
            row("VRAM (AdapterRAM)",hx(gpuVRAM,8),vv.str());
        }
        row("PNP Device ID",    "0x--",gpuPCI_ID);
        row("Uso GPU (load)",   "0x--",gpuLoad);
        row("Temperatura GPU",  "0x--",gpuTemp);
        row("IRQ asignada",     "0x0B","IRQ 11  compartida PCIe");
        row("Bus de video",     "0x--","PCI Express  (Bus Master DMA)");

        cout<<"\n"<<BOLD<<YEL<<"  \u2550\u2550 MONITORES FISICOS CONECTADOS  ("
            <<g_monitors.size()<<")"<<RST<<"\n";
        sep('=',80);
        cout<<GRY<<"  "
            <<pad("DISP.",14)<<pad("RESOLUCION",14)<<pad("FREC",8)
            <<pad("BPP",6)<<pad("DPI",10)<<pad("POSICION",18)<<"PRIMARIO"<<RST<<"\n";
        sep();
        for(size_t mi=0;mi<g_monitors.size();mi++){
            auto& mo=g_monitors[mi];
            ostringstream res,pos,dpis;
            res<<mo.anchoPx<<"x"<<mo.altoPx;
            pos<<mo.rcMonitor.left<<","<<mo.rcMonitor.top;
            dpis<<mo.dpiX<<"x"<<mo.dpiY;
            string prim = mo.esPrimario ? GRN+"SI"+RST : "no";
            cout<<"  "
                <<pad(to_string(mi+1)+": "+mo.dispositivo,14)
                <<pad(res.str(),14)
                <<pad(to_string(mo.frecHz)+"Hz",8)
                <<pad(to_string(mo.bpp)+"b",6)
                <<pad(dpis.str(),10)
                <<pad(pos.str(),18)
                <<prim<<"\n";
            int wPx=mo.rcWork.right-mo.rcWork.left;
            int hPx=mo.rcWork.bottom-mo.rcWork.top;
            cout<<"  "<<DIM
                <<"    Area trabajo: "<<wPx<<"x"<<hPx<<"px"
                <<"  VRAM offset: "<<hx((unsigned long long)(mo.rcMonitor.left*mo.altoPx*(mo.bpp/8)),8)
                <<"  Handle: "<<hx((unsigned long long)(uintptr_t)mo.hmon,8)
                <<RST<<"\n";
        }

        header("DATOS  --  DISPLAY Y FRAMEBUFFER  (pantalla primaria)");
        row("Adaptador activo",  "0x--",adapterName);
        row("Resolucion activa",
            hx((unsigned short)resX,4)+" x "+hx((unsigned short)resY,4),
            to_string(resX)+" x "+to_string(resY)+" px");
        row("Escritorio virtual","0x--",to_string(virtW)+" x "+to_string(virtH)+" px");
        row("Profundidad color", hx(dm.dmBitsPerPel),
            to_string(dm.dmBitsPerPel)+" bpp  "+(dm.dmBitsPerPel==32?"True Color":"High Color"));
        row("Frecuencia refresco",hx(dm.dmDisplayFrequency),
            to_string(dm.dmDisplayFrequency)+" Hz  ("+to_string(msFrame)+" ms/frame)");
        row("Numero de monitores",hx(mons),to_string(mons));
        row("DPI horizontal",    hx(dpiX),to_string(dpiX)+" dpi");
        row("DPI vertical",      hx(dpiY),to_string(dpiY)+" dpi");
        {
            string ori=dm.dmDisplayOrientation==0?"Normal  0 deg":
                       dm.dmDisplayOrientation==1?"Rotado  90 deg":
                       dm.dmDisplayOrientation==2?"Invertido  180 deg":"Rotado  270 deg";
            row("Orientacion",hx(dm.dmDisplayOrientation),ori);
        }
        row("Framebuffer total", hx((unsigned long long)fbSz,8),
            to_string(fbSz/1024/1024)+" MB  ("+to_string(resX)+"x"+to_string(resY)+" x "+to_string(bpp)+"B)");

        header("DATOS  --  PIXEL BAJO CURSOR");
        row("Cursor X",hx((unsigned short)cur.x,4),to_string(cur.x)+" px");
        row("Cursor Y",hx((unsigned short)cur.y,4),to_string(cur.y)+" px");
        row("Pixel R", hx(R),to_string(R));
        row("Pixel G", hx(G),to_string(G));
        row("Pixel B", hx(B),to_string(B));
        row("Valor RGB",hx(px,6),"R="+to_string(R)+" G="+to_string(G)+" B="+to_string(B));
        row("Dir. VRAM estimada",hx((unsigned long long)voff,10),to_string(voff)+" bytes");

        cout<<"\n"<<BOLD<<MGN<<"  \u2550\u2550 VENTANAS ABIERTAS  ("
            <<g_ventanas.size()<<" visibles)"<<RST<<"\n";
        sep('=',80);
        cout<<GRY<<"  "
            <<pad("HWND",12)<<pad("PID",8)<<pad("PROCESO",20)
            <<pad("ESTADO",14)<<pad("POSICION / SIZE",20)<<"TITULO"<<RST<<"\n";
        sep();

        int maxVent=18;
        int shown=0;
        for(auto& v : g_ventanas){
            if(shown>=maxVent) break;
            int w=v.rect.right-v.rect.left;
            int h=v.rect.bottom-v.rect.top;
            ostringstream posStr;
            posStr<<"("<<v.rect.left<<","<<v.rect.top<<") "<<w<<"x"<<h;
            string hwndStr=hx((unsigned long long)(uintptr_t)v.hwnd,8);

            cout<<"\r  ";
            cout<<BOLD<<WHT<<pad(hwndStr,12)<<RST;
            cout<<GRY<<pad(to_string(v.pid),8)<<RST;
            cout<<pad(v.proceso,20);
            if(v.esForeground) cout<<BOLD<<GRN<<pad("[ACTIVA]",14)<<RST;
            else if(v.estado=="Maximizada") cout<<YEL<<pad("MAX",14)<<RST;
            else if(v.estado=="Minimizada") cout<<DIM<<pad("MIN",14)<<RST;
            else cout<<pad("Normal",14);
            cout<<GRY<<pad(posStr.str(),20)<<RST;
            string tit=v.titulo;
            if((int)tit.size()>25) tit=tit.substr(0,22)+"...";
            if(v.esForeground) cout<<BOLD<<WHT<<tit<<RST;
            else               cout<<tit;
            cout<<"\n";
            shown++;
        }
        if((int)g_ventanas.size()>maxVent){
            cout<<"  "<<DIM<<"... +"<<(g_ventanas.size()-maxVent)<<" ventanas mas"<<RST<<"\n";
        }

        cout<<"\n"<<BOLD<<CYN<<"  \u2550\u2550 HISTORIAL PRIMER PLANO (ultimas "
            <<histFG.size()<<")"<<RST<<"\n";
        sep();
        for(int hi=(int)histFG.size()-1;hi>=0;hi--){
            string marker=(hi==(int)histFG.size()-1)?GRN+">> "+RST:DIM+"   "+RST;
            string tit=histFG[hi];
            if((int)tit.size()>70) tit=tit.substr(0,67)+"...";
            cout<<"  "<<marker<<tit<<"\n";
        }

        header("ESTADO");
        row("Pantalla activa",        "0x01",GRN+"SI"+RST);
        row("Buffer de video",        "0x00","libre");
        row("Vertical sync (VSync)",  "0x01",GRN+"activo en refresco"+RST);
        row("Error de sincronizacion","0x00","sin error");
        row("Modo WDDM",              "0x01",GRN+"activo (GPU moderna)"+RST);
        row("Ventanas activas",       hx((unsigned long long)g_ventanas.size(),4),
            to_string(g_ventanas.size())+" ventanas visibles");

        header("COMANDO / CONTROL");
        row("Iniciar DMA frame",    "0xC8","GPU DMA -> VRAM -> pantalla");
        row("Activar pantalla",     "0x01",GRN+"SI"+RST);
        row("IRQ VSync habilitada", "0x01","bit VSync IRQ ON");
        row("Ancho banda requerido",hx(bwMB,4),to_string(bwMB)+" MB/s");

        seccionIRQ("INTERRUPCIONES  --  IRQ 11  (vector 0x73)",{
            {"IRQ 11","0x73","Vertical Retrace  (VSync)",     true},
            {"IRQ 11","0x73","Refresco de pantalla completo", true},
            {"IRQ 11","0x73","DMA framebuffer -> VRAM listo", true},
            {"IRQ 11","0x73","Error de sincronizacion H/V",   false},
            {"IRQ 11","0x73","Cambio de resolucion",          false},
            {"IRQ 11","0x73","Pantalla apagada/encendida",    false},
        });

        seccionDMA("DMA  --  ACCESO DIRECTO A MEMORIA  (PCIe Bus Master)",
            "DMA GPU  (PCIe Bus Master)",
            "Modo Bloque  --  framebuffer completo",
            hx((unsigned long long)voff,8)+"  (VRAM base)",
            (unsigned long long)fbSz,(unsigned long long)fbSz,
            true,false,"");
        cout<<"  "<<DIM
            <<"Ancho banda: "<<bwMB<<" MB/s"
            <<"  ("<<dm.dmDisplayFrequency<<" fps  x  "<<fbSz/1024/1024<<" MB/frame)\n"
            <<"  Flujo: CPU escribe RAM -> DMA PCIe -> VRAM -> GPU -> IRQ 11\n"
            <<"  VRAM total GPU: "<<(gpuVRAM>0?to_string(gpuVRAM/1024/1024)+" MB":"N/A")
            <<"\n"<<RST;

        sep('=',80);
    }
}

// ══════════════════════════════════════════════════════════════
//  DISCO DURO  (MEJORADO  --  ECC + DISPLAY ESTABLE)
// ══════════════════════════════════════════════════════════════

// Tiempo (ms) que el ultimo evento permanece visible en pantalla
// sin ser reemplazado.  120 segundos = 2 minutos.
static const ULONGLONG DISPLAY_HOLD_MS = 120000ULL;

// ── Calcula el codigo ECC Hamming(72,64) para un bloque de 8 bytes ──
// Retorna los 8 bits de paridad p1..p8 como un byte.
// Este es el mismo esquema que usan los modulos DRAM ECC y muchos
// controladores ATA/SATA para la integridad del cache de disco.
static unsigned char calcECC(const unsigned char* data, int len) {
    // XOR acumulado de todos los bytes (paridad simple por columna)
    unsigned char xorAcum = 0;
    for(int i = 0; i < len; i++) xorAcum ^= data[i];

    // Bits de paridad Hamming sobre las 8 columnas de bits
    unsigned char p = 0;
    for(int bit = 0; bit < 8; bit++) {
        int par = 0;
        for(int i = 0; i < len; i++) {
            if((data[i] >> bit) & 1) par ^= 1;
        }
        if(par) p |= (1 << bit);
    }
    // Combinar: XOR global en bit8 (overflow en byte -> lo incluimos en p)
    p ^= xorAcum;
    return p;
}

// ── Simula el sindrome ECC para detectar/corregir errores de 1 bit ──
// Retorna: 0 = sin error, >0 = posicion del bit erroneo (1-indexed),
//          0xFF = error de 2 bits (no corregible)
static unsigned char sdromeECC(unsigned char eccCalculado,
                                 unsigned char eccAlmacenado) {
    unsigned char sindrome = eccCalculado ^ eccAlmacenado;
    if(sindrome == 0) return 0;           // sin error
    // Si exactamente 1 bit diferente -> error corregible de 1 bit
    if((sindrome & (sindrome - 1)) == 0) return sindrome; // potencia de 2
    return 0xFF;                           // error de 2 bits
}

struct EventoArchivo {
    string   nombre;
    string   extension;
    string   operacion;
    unsigned long long tamBytes;
    unsigned long long lbaEstimado;
    unsigned long long sectores;
    double   velMBs;
    ULONGLONG tickInicio;
    ULONGLONG tickFin;
    double   durMs;
    string   timestamp;
    bool     completo;
    // Campos ECC del sector
    unsigned char eccData[8];   // primeros 8 bytes del "sector simulado"
    unsigned char eccCalc;      // ECC calculado sobre eccData
    unsigned char eccStore;     // ECC almacenado (igual a eccCalc, sin errores)
    unsigned char eccSindrome;  // sindrome: 0=OK, >0=error
    string        eccEstado;    // descripcion legible
};

unsigned long long getFileSizeByName(const string& path){
    WIN32_FILE_ATTRIBUTE_DATA fa={};
    wstring wp(path.begin(),path.end());
    if(GetFileAttributesExW(wp.c_str(),GetFileExInfoStandard,&fa)){
        return ((unsigned long long)fa.nFileSizeHigh<<32)|fa.nFileSizeLow;
    }
    return 0;
}

string getTimestamp(){
    SYSTEMTIME st; GetLocalTime(&st);
    char buf[32];
    sprintf(buf,"%02d:%02d:%02d.%03d",st.wHour,st.wMinute,st.wSecond,st.wMilliseconds);
    return buf;
}

string getExtension(const string& nombre){
    size_t pos=nombre.rfind('.');
    if(pos==string::npos) return "(sin ext)";
    string ext=nombre.substr(pos+1);
    for(auto& c:ext) c=(char)toupper((unsigned char)c);
    return ext;
}

// ── Genera datos ECC simulados para un evento de archivo ─────────────
// Deriva los 8 bytes del "sector simulado" del LBA y el tamanio del
// archivo, de forma determinista pero variada.
void generarECC(EventoArchivo& ev) {
    // Construir bloque de 8 bytes representativo del sector
    unsigned long long lba = ev.lbaEstimado;
    unsigned long long tam = ev.tamBytes;
    ev.eccData[0] = (unsigned char)( lba        & 0xFF);
    ev.eccData[1] = (unsigned char)((lba >>  8) & 0xFF);
    ev.eccData[2] = (unsigned char)((lba >> 16) & 0xFF);
    ev.eccData[3] = (unsigned char)((lba >> 24) & 0xFF);
    ev.eccData[4] = (unsigned char)( tam        & 0xFF);
    ev.eccData[5] = (unsigned char)((tam >>  8) & 0xFF);
    ev.eccData[6] = (unsigned char)((tam >> 16) & 0xFF);
    ev.eccData[7] = (unsigned char)((tam >> 24) & 0xFF);

    ev.eccCalc    = calcECC(ev.eccData, 8);
    ev.eccStore   = ev.eccCalc;   // disco sano: ECC almacenado == calculado
    ev.eccSindrome= sdromeECC(ev.eccCalc, ev.eccStore);
    ev.eccEstado  = "OK  --  sin errores detectados";
}

// ── Imprime la seccion ECC completa ──────────────────────────────────
void seccionECC(const EventoArchivo& ev, unsigned long diskBPS) {
    cout << "\n" << BOLD << CYN << "  \u250c\u2500 ECC  --  ERROR CORRECTION CODE  (sector "
         << ev.lbaEstimado << ")" << RST << "\n";
    sep();
    cout << GRY << "  "
         << pad("CAMPO", 30) << pad("HEX", 14) << "VALOR" << RST << "\n";
    sep();

    // Datos del sector (8 bytes representativos)
    ostringstream dataStr;
    for(int i = 0; i < 8; i++) {
        dataStr << hx(ev.eccData[i]) << " ";
    }
    row("Datos sector (8 bytes)", "0x--", dataStr.str());
    row("Bytes/sector",           hx((unsigned long long)diskBPS, 4),
        to_string(diskBPS) + " bytes  (sector fisico)");

    // Bits de paridad Hamming
    cout << "\n";
    row("Algoritmo ECC",          "0x--", "Hamming(72,64)  --  SECDED");
    row("ECC calculado (dato)",   hx(ev.eccCalc,  2),
        "paridad Hamming sobre 64 bits del sector");
    row("ECC almacenado (disco)", hx(ev.eccStore, 2),
        "valor grabado en los 8 bits ECC del sector");

    // Sindrome
    unsigned char sind = ev.eccSindrome;
    if(sind == 0) {
        row("Sindrome ECC",        "0x00",
            GRN + "0x00  --  NINGUN ERROR  (dato integro)" + RST);
        row("Resultado verificacion","0x00", GRN + "CORRECTO" + RST);
        row("Accion correctora",   "0x00", "ninguna necesaria");
    } else if(sind == 0xFF) {
        row("Sindrome ECC",        RED+"0xFF"+RST,
            RED + "ERROR DE 2 BITS  --  NO CORREGIBLE  (UE)" + RST, true);
        row("Resultado verificacion","0xFF", RED + "ERROR INCORREGIBLE" + RST, true);
        row("Accion correctora",   "0xFF", RED + "sector marcado como bad block" + RST, true);
    } else {
        ostringstream sb;
        sb << "bit " << __builtin_ctz(sind) + 1
           << "  (mascara " << hx(sind) << ")  --  error de 1 bit corregido";
        row("Sindrome ECC",        hx(sind, 2), YEL + sb.str() + RST);
        row("Resultado verificacion",hx(sind,2), YEL + "ERROR 1 BIT  --  CORREGIDO (CE)" + RST);
        row("Accion correctora",   hx(sind, 2), YEL + "bit invertido restaurado automaticamente" + RST);
    }

    // Campos estandar de un sector ATA con ECC
    row("Tamano campo ECC",        "0x08", "8 bits  (Hamming SECDED sobre 64b)");
    row("Capacidad deteccion",     "0x02", "hasta 2 bits por sector  (deteccion)");
    row("Capacidad correccion",    "0x01", "1 bit por sector  (correccion)");
    row("ECC habilitado",          "0x01", GRN + "SI  --  activo en controlador" + RST);
    row("Errores corregidos total","0x00", "0  (sin historial de errores en esta sesion)");
    row("Errores incorregibles",   "0x00", "0  (disco sano)");

    // Tabla de bits de paridad
    cout << "\n  " << DIM
         << "Bits de paridad  (p1..p8  ->  posiciones 1,2,4,8,16,32,64,128):\n";
    cout << "  ";
    for(int b = 7; b >= 0; b--) {
        int bit = (ev.eccCalc >> b) & 1;
        cout << (bit ? GRN : GRY) << "p" << (b+1) << "=" << bit << " " << RST;
    }
    cout << "\n" << RST;

    // Nota informativa
    cout << "  " << DIM
         << "ECC SECDED: Single-Error Correcting, Double-Error Detecting.\n"
         << "  Cada sector de " << diskBPS << " bytes agrega 8 bits ECC en su campo de redundancia.\n"
         << "  El controlador verifica ECC en cada lectura DMA antes de pasar datos a RAM.\n"
         << RST;
}

void runDisco() {
    SetConsoleTitleA("DISCO DURO -- Registros del controlador");
    SetConsoleOutputCP(65001);
    enableColors();

    WMI wmi;
    string diskModel="N/A",diskSerial="N/A",diskIface="N/A";
    string diskMedia="N/A",diskFirmware="N/A",diskStatus="N/A";
    string diskPartitions="N/A",diskPnpID="N/A";
    unsigned long long diskSize=0;
    unsigned long diskBPS=0;
    unsigned long long diskSectors=0;
    unsigned long diskCyl=0,diskTPC=0,diskSPT=0;

    if(wmi.ok){
        auto pE=wmi.query(L"SELECT * FROM Win32_DiskDrive WHERE Index=0");
        if(pE){
            IWbemClassObject* pO=nullptr; ULONG ret=0;
            if(SUCCEEDED(pE->Next(WBEM_INFINITE,1,&pO,&ret))&&ret){
                diskModel    =WMI::str(pO,L"Model");
                diskSerial   =WMI::str(pO,L"SerialNumber");
                diskIface    =WMI::str(pO,L"InterfaceType");
                diskMedia    =WMI::str(pO,L"MediaType");
                diskFirmware =WMI::str(pO,L"FirmwareRevision");
                diskStatus   =WMI::str(pO,L"Status");
                diskPnpID    =WMI::str(pO,L"PNPDeviceID");
                diskSize     =WMI::ull(pO,L"Size");
                diskBPS      =(unsigned long)WMI::ull(pO,L"BytesPerSector");
                diskSectors  =WMI::ull(pO,L"TotalSectors");
                diskCyl      =(unsigned long)WMI::ull(pO,L"TotalCylinders");
                diskTPC      =(unsigned long)WMI::ull(pO,L"TracksPerCylinder");
                diskSPT      =(unsigned long)WMI::ull(pO,L"SectorsPerTrack");
                unsigned long long np=WMI::ull(pO,L"Partitions");
                diskPartitions=np?to_string(np):"N/A";
                pO->Release();
            }
            pE->Release();
        }
    }
    if(diskBPS==0) diskBPS=512;

    double velLectMB=0.0, velEscMB=0.0;
    {
        string iface=diskIface;
        for(auto& ch:iface) ch=(char)toupper((unsigned char)ch);
        string model=diskModel;
        for(auto& ch:model) ch=(char)toupper((unsigned char)ch);
        if(iface.find("USB")!=string::npos){
            velLectMB=400; velEscMB=200;
        } else if(iface.find("IDE")!=string::npos){
            velLectMB=133; velEscMB=100;
        } else {
            if(model.find("NVME")!=string::npos||
               model.find("NVM")!=string::npos||
               model.find("PCIE")!=string::npos){
                velLectMB=3500; velEscMB=3000;
            } else if(diskBPS>=4096){
                velLectMB=560;  velEscMB=530;
            } else {
                velLectMB=150;  velEscMB=120;
            }
        }
    }

    // ── ReadDirectoryChangesW (SOLO LECTURA de notificaciones del SO) ──
    // Este programa NO crea, mueve, copia ni elimina ningun archivo.
    // Unicamente observa los cambios que el usuario realiza manualmente.
    HANDLE hDir = CreateFileW(
        L"C:\\",
        FILE_LIST_DIRECTORY,
        FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
        NULL, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OVERLAPPED,
        NULL);

    OVERLAPPED ov={};
    ov.hEvent = CreateEvent(NULL,TRUE,FALSE,NULL);
    vector<BYTE> changeBuf(65536);

    bool rdcOk=(hDir!=INVALID_HANDLE_VALUE);
    if(rdcOk){
        ReadDirectoryChangesW(hDir,changeBuf.data(),(DWORD)changeBuf.size(),
            TRUE,
            FILE_NOTIFY_CHANGE_FILE_NAME|
            FILE_NOTIFY_CHANGE_DIR_NAME|
            FILE_NOTIFY_CHANGE_SIZE|
            FILE_NOTIFY_CHANGE_LAST_WRITE|
            FILE_NOTIFY_CHANGE_CREATION,
            NULL,&ov,NULL);
    }

    deque<EventoArchivo> histArchivos;

    int sample=0;
    unsigned long long prevLibre=0;
    int dmaPhase=0;
    ULONGLONG dmaLastTick=0;

    {
        ULARGE_INTEGER l,t,tl;
        GetDiskFreeSpaceExW(L"C:\\",&l,&t,&tl);
        prevLibre=tl.QuadPart;
    }

    EventoArchivo xferActual={};
    bool hayXfer=false;
    ULONGLONG ultimoEventoTick=0;

    // ── Control de refresco: solo redibujar cuando hay razon ─────────
    // Se redibuja si: hay nuevo evento de archivo, o cada
    // REFRESH_INTERVAL_MS si ya hay un evento visible.
    static const ULONGLONG REFRESH_INTERVAL_MS = 5000ULL; // 5 seg
    ULONGLONG ultimoRefreshTick = 0;

    // ── Debounce: ignorar notificaciones duplicadas del mismo archivo ──
    // Windows puede enviar CREADO + MODIFICADO + MODIFICADO... para
    // un solo archivo. Guardamos el nombre y tick del ultimo evento
    // aceptado; si llega otro del mismo archivo antes de DEBOUNCE_MS,
    // solo actualizamos el tamanio pero NO reseteamos ultimoEventoTick.
    static const ULONGLONG DEBOUNCE_MS = 4000ULL; // 4 seg de gracia
    string debounceNombre = "";
    ULONGLONG debounceTick = 0;

    while(true){
        // Esperar notificacion de archivo con timeout de 2 segundos
        if(rdcOk){
            WaitForSingleObject(ov.hEvent, 2000);
        } else {
            Sleep(2000);
        }
        sample++;

        bool nuevoEvento = false;

        // ── Procesar notificaciones del SO (el programa NO toca archivos)
        if(rdcOk){
            DWORD bytesRet=0;
            if(GetOverlappedResult(hDir,&ov,&bytesRet,FALSE)&&bytesRet>0){
                BYTE* ptr=changeBuf.data();
                while(ptr){
                    FILE_NOTIFY_INFORMATION* fni=(FILE_NOTIFY_INFORMATION*)ptr;
                    int sz=WideCharToMultiByte(CP_UTF8,0,fni->FileName,
                        fni->FileNameLength/2,nullptr,0,nullptr,nullptr);
                    string fname(sz,0);
                    WideCharToMultiByte(CP_UTF8,0,fni->FileName,
                        fni->FileNameLength/2,&fname[0],sz,nullptr,nullptr);

                    string ext=getExtension(fname);
                    bool esArchivo=(ext!="(sin ext)")||fname.find('.')!=string::npos;

                    if(esArchivo){
                        string op="MODIFICADO";
                        switch(fni->Action){
                            case FILE_ACTION_ADDED:           op="CREADO";          break;
                            case FILE_ACTION_REMOVED:         op="ELIMINADO";       break;
                            case FILE_ACTION_MODIFIED:        op="MODIFICADO";      break;
                            case FILE_ACTION_RENAMED_OLD_NAME:op="RENOMBRADO(from)";break;
                            case FILE_ACTION_RENAMED_NEW_NAME:op="RENOMBRADO(to)";  break;
                        }

                        unsigned long long fsz=0;
                        if(fni->Action!=FILE_ACTION_REMOVED){
                            string fullPath="C:\\"+fname;
                            fsz=getFileSizeByName(fullPath);
                        }

                        unsigned long long sectEst=(fsz>0)?((fsz+diskBPS-1)/diskBPS):1;
                        ULARGE_INTEGER l2,t2,tl2;
                        GetDiskFreeSpaceExW(L"C:\\",&l2,&t2,&tl2);
                        unsigned long long usadoBytes=t2.QuadPart-tl2.QuadPart;
                        unsigned long long lbaEst=usadoBytes/diskBPS;

                        double velEst=(op=="CREADO"||op=="MODIFICADO")?velEscMB:velLectMB;
                        double durEstMs=(velEst>0&&fsz>0)?
                            ((double)fsz/(velEst*1024.0*1024.0))*1000.0 : 0.0;

                        EventoArchivo ev;
                        ev.nombre      = fname;
                        ev.extension   = ext;
                        ev.operacion   = op;
                        ev.tamBytes    = fsz;
                        ev.lbaEstimado = lbaEst;
                        ev.sectores    = sectEst;
                        ev.velMBs      = velEst;
                        ev.tickInicio  = GetTickCount64();
                        ev.tickFin     = ev.tickInicio+(ULONGLONG)durEstMs;
                        ev.durMs       = durEstMs;
                        ev.timestamp   = getTimestamp();
                        ev.completo    = false;

                        // Generar datos ECC para este sector
                        generarECC(ev);

                        ULONGLONG ahoraEv = GetTickCount64();
                        bool esDuplicado  = (fname == debounceNombre)
                                         && (ahoraEv - debounceTick < DEBOUNCE_MS);

                        if(!esDuplicado) {
                            // Evento genuinamente nuevo: registrar todo
                            histArchivos.push_front(ev);
                            if(histArchivos.size()>20) histArchivos.pop_back();

                            xferActual       = ev;
                            hayXfer          = true;
                            ultimoEventoTick = ahoraEv;
                            debounceTick     = ahoraEv;
                            debounceNombre   = fname;
                            nuevoEvento      = true;
                        } else {
                            // Notificacion duplicada del mismo archivo:
                            // actualizar solo el tamanio (el archivo puede
                            // seguir creciendo) pero NO mover ultimoEventoTick,
                            // para que el display_hold cuente desde el PRIMER
                            // evento y no se reinicie con cada MODIFICADO.
                            xferActual.tamBytes = ev.tamBytes;
                            xferActual.sectores = ev.sectores;
                            generarECC(xferActual);
                            if(!histArchivos.empty()){
                                histArchivos.front().tamBytes = ev.tamBytes;
                                histArchivos.front().sectores = ev.sectores;
                            }
                            // NO actualizamos ultimoEventoTick ni nuevoEvento
                        }
                    }

                    if(fni->NextEntryOffset==0) break;
                    ptr+=fni->NextEntryOffset;
                }

                ResetEvent(ov.hEvent);
                ReadDirectoryChangesW(hDir,changeBuf.data(),(DWORD)changeBuf.size(),
                    TRUE,
                    FILE_NOTIFY_CHANGE_FILE_NAME|
                    FILE_NOTIFY_CHANGE_DIR_NAME|
                    FILE_NOTIFY_CHANGE_SIZE|
                    FILE_NOTIFY_CHANGE_LAST_WRITE|
                    FILE_NOTIFY_CHANGE_CREATION,
                    NULL,&ov,NULL);
            }
        }

        // Marcar xfer completo si paso la duracion estimada.
        // Si durMs == 0 (ELIMINADO, archivo vacio, o muy pequenio) NO usamos
        // el timer: solo DISPLAY_HOLD_MS decide cuando deja de ser "reciente".
        // Esto evita que ELIMINADO se marque completo a los 2 segundos.
        if(hayXfer && !xferActual.completo && xferActual.durMs > 100.0){
            ULONGLONG ahora=GetTickCount64();
            if(ahora-xferActual.tickInicio>(ULONGLONG)(xferActual.durMs+2000)){
                xferActual.completo=true;
                if(!histArchivos.empty()) histArchivos.front().completo=true;
            }
        }

        ULONGLONG ahoraTick = GetTickCount64();

        // ── Decidir si redibujar:
        //    - Siempre si hubo un nuevo evento de archivo
        //    - Si hay evento activo: redibujar cada REFRESH_INTERVAL_MS
        //    - Si no hay evento: NO redibujar (pantalla quieta)
        bool debeRedibujar = false;
        if(nuevoEvento) {
            debeRedibujar = true;
        } else if(hayXfer && (ahoraTick - ultimoRefreshTick >= REFRESH_INTERVAL_MS)) {
            debeRedibujar = true;
        }
        if(!debeRedibujar) continue;
        ultimoRefreshTick = ahoraTick;

        // Espacio en disco
        ULARGE_INTEGER libre,total,totalLibre;
        GetDiskFreeSpaceExW(L"C:\\",&libre,&total,&totalLibre);
        double totalGB =total.QuadPart    /(1024.0*1024.0*1024.0);
        double libreGB =totalLibre.QuadPart/(1024.0*1024.0*1024.0);
        double usadoGB =totalGB-libreGB;
        double pct     =(totalGB>0)?(usadoGB/totalGB)*100.0:0.0;

        long long diff=(long long)totalLibre.QuadPart-(long long)prevLibre;
        long long deltaLibreKB=diff/1024;
        prevLibre=totalLibre.QuadPart;

        if(ahoraTick-dmaLastTick>=800){ dmaPhase=(dmaPhase+1)%4; dmaLastTick=ahoraTick; }

        ULONGLONG tiempoDesdeEvento = hayXfer ? (ahoraTick - ultimoEventoTick) : 0;
        unsigned long long segsDesdeEvento = tiempoDesdeEvento / 1000ULL;
        bool eventoReciente = hayXfer && (tiempoDesdeEvento < DISPLAY_HOLD_MS);

        wchar_t wVol[256]={},wFs[256]={};
        DWORD serial=0,maxComp=0,flags=0;
        GetVolumeInformationW(L"C:\\",wVol,256,&serial,&maxComp,&flags,wFs,256);
        string volNom(wVol,wVol+wcslen(wVol));
        string volFs(wFs,wFs+wcslen(wFs));

        unsigned long long lba=diskBPS>0
            ?(unsigned long long)(usadoGB*1024.0*1024.0*1024.0)/diskBPS
            :(unsigned long long)(usadoGB*1024.0*1024.0*1024.0)/512;

        int fill=(int)(pct/100.0*40);
        string barra="["+string(fill,'#')+string(40-fill,'.')+"]";

        HANDLE hDisk=CreateFileW(L"\\\\.\\C:",GENERIC_READ,
            FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,0,NULL);
        DISK_GEOMETRY geo={}; DWORD bytesRet2=0; bool geoOk=false;
        if(hDisk!=INVALID_HANDLE_VALUE){
            geoOk=DeviceIoControl(hDisk,IOCTL_DISK_GET_DRIVE_GEOMETRY,
                NULL,0,&geo,sizeof geo,&bytesRet2,NULL);
            CloseHandle(hDisk);
        }

        unsigned long long dmaBytes=diskBPS>0?diskBPS:512;
        unsigned long long dmaSectores=xferActual.sectores;
        unsigned long long dmaTotalBytes=xferActual.tamBytes;
        unsigned long long dmaBaseAddr=xferActual.lbaEstimado*dmaBytes;

        string dmaFaseStr, dmaModoStr, dmaCanalStr;
        bool dmaActivo=false;
        switch(dmaPhase){
            case 0: dmaFaseStr="FASE 1: CPU escribe LBA en reg. 0x1F3-0x1F6";
                    dmaModoStr="PIO -> preparando comando DMA";
                    dmaCanalStr="Bus Master IDE  (iniciando)"; break;
            case 1: dmaFaseStr="FASE 2: CPU envia cmd 0xC8  READ/WRITE DMA";
                    dmaModoStr="Bus Master DMA  activado";
                    dmaCanalStr="Canal 2  IDE/SATA  Bus Master";
                    dmaActivo=true; break;
            case 2: dmaFaseStr="FASE 3: DMA transfiere sectores a RAM";
                    dmaModoStr="Modo Bloque  Bus Master DMA  UDMA/133";
                    dmaCanalStr="Canal 2  IDE/SATA  transferencia activa";
                    dmaActivo=true; break;
            case 3: dmaFaseStr="FASE 4: IRQ 14 notifica CPU  --  DMA completo";
                    dmaModoStr="Bus Master DMA  completado";
                    dmaCanalStr="Canal 2  IDE/SATA  Bus Master"; break;
        }

        system("cls");
        sep('=',80);
        cout<<BOLD<<WHT<<"  DISCO DURO  ATA/SATA  IRQ 14  (0x76)"
            <<"   evento #"<<sample<<RST<<"\n";
        sep('=',80);

        header("DISCO FISICO  --  Win32_DiskDrive");
        row("Modelo",           "0x--",diskModel);
        row("Numero de serie",  "0x--",diskSerial.empty()?"N/A":diskSerial);
        row("Firmware",         "0x--",diskFirmware);
        row("Interfaz",         "0x--",diskIface);
        row("PNP Device ID",    "0x--",diskPnpID);
        row("Tipo de medio",    "0x--",diskMedia);
        row("Estado SMART",     "0x--",diskStatus);
        row("Particiones",      "0x--",diskPartitions);
        {
            ostringstream sv;
            if(diskSize>0) sv<<diskSize/1024/1024/1024<<" GB  ("<<diskSize<<" bytes)";
            else sv<<"N/A";
            row("Capacidad total",hx(diskSize,10),sv.str());
        }
        row("Bytes/sector",     hx(diskBPS,4),     to_string(diskBPS)+" bytes");
        row("Total sectores",   hx(diskSectors,10),diskSectors?to_string(diskSectors):"N/A");
        row("Cilindros",        hx(diskCyl,6),     diskCyl?to_string(diskCyl):"N/A");
        row("Pistas/cilindro",  hx(diskTPC,4),     diskTPC?to_string(diskTPC):"N/A");
        row("Sectores/pista",   hx(diskSPT,4),     diskSPT?to_string(diskSPT):"N/A");
        {
            ostringstream vl,ve;
            vl<<fixed<<setprecision(1)<<velLectMB<<" MB/s  (max interfaz)";
            ve<<fixed<<setprecision(1)<<velEscMB <<" MB/s  (max interfaz)";
            row("Velocidad lectura max", hx((unsigned long long)velLectMB,4),vl.str());
            row("Velocidad escritura max",hx((unsigned long long)velEscMB, 4),ve.str());
        }
        if(geoOk){
            row("Cilindros (IOCTL)",hx((unsigned long long)geo.Cylinders.QuadPart,8),
                to_string(geo.Cylinders.QuadPart));
            row("Cabezales",       hx((unsigned long long)geo.TracksPerCylinder,4),
                to_string(geo.TracksPerCylinder));
        }

        header("DATOS  (espacio logico  C:)");
        row("Volumen C:",        "0x--",volNom.empty()?"(sin etiqueta)":volNom);
        row("Sistema archivos",  "0x--",volFs);
        row("Serial volumen",    hx(serial,8),to_string(serial));
        row("Capacidad total",   hx(total.QuadPart,10),to_string((int)totalGB)+" GB");
        row("Espacio usado",
            hx((unsigned long long)(usadoGB*1024*1024*1024),10),
            to_string((int)usadoGB)+" GB  ("+to_string((int)pct)+"%)");
        row("Espacio libre",     hx(totalLibre.QuadPart,10),to_string((int)libreGB)+" GB");
        cout<<"  Uso: "<<GRY<<barra<<RST<<fixed<<setprecision(1)<<" "<<pct<<"%\n";
        row("Dir. sector  LBA",  hx(lba,10),to_string(lba)+" sector estimado");
        {
            string delta_str=(deltaLibreKB>0?GRN+"LIBERADOS +":
                             (deltaLibreKB<0?RED+"USADO -":DIM+"SIN CAMBIO "))
                             +to_string(abs(deltaLibreKB))+" KB"+RST;
            row("** CAMBIO **",  hx((unsigned long long)abs(deltaLibreKB),6),delta_str,
                deltaLibreKB<0);
        }

        // ─── TRANSFERENCIA DE ARCHIVO ACTUAL ──────────────────────
        cout<<"\n"<<BOLD<<YEL
            <<"  \u2550\u2550 TRANSFERENCIA DE ARCHIVO EN TIEMPO REAL"<<RST<<"\n";
        sep('=',80);

        if(!hayXfer){
            cout<<DIM
                <<"  Esperando actividad de archivos en C:\\\n"
                <<"  Crea, copia, modifica o elimina cualquier archivo manualmente en C:\\\n"
                <<"  El programa NO crea ni elimina archivos por si mismo.\n"
                <<RST;
        } else {
            auto& x=xferActual;
            string opColor;
            if(x.operacion=="CREADO")     opColor=GRN+x.operacion+RST;
            else if(x.operacion=="ELIMINADO") opColor=RED+x.operacion+RST;
            else if(x.operacion.find("RENOMBRADO")!=string::npos) opColor=YEL+x.operacion+RST;
            else opColor=CYN+x.operacion+RST;

            ULONGLONG elapsed=GetTickCount64()-x.tickInicio;
            // durMs == 0 significa archivo eliminado o de 0 bytes:
            // mostrar barra llena instantaneamente (la operacion es atomica).
            double progPct=100.0;
            if(x.durMs > 100.0) progPct=min(100.0,(double)elapsed/x.durMs*100.0);
            if(x.completo) progPct=100.0;
            int progFill=(int)(progPct/100.0*40);
            string progBarra;
            if(x.completo || x.durMs <= 100.0)
                progBarra=GRN+"["+string(40,'=')+"]"+RST;
            else
                progBarra=YEL+"["+string(progFill,'=')
                              +string(40-progFill,'.')+"]"+RST;

            string estadoDisplay;
            if(!x.completo && x.durMs > 100.0){
                // Transferencia con duracion real estimada: en progreso
                estadoDisplay = YEL+"EN PROGRESO"+RST;
            } else if(eventoReciente){
                // Completo (o durMs==0): visible mientras dure DISPLAY_HOLD_MS
                ostringstream ss;
                ss << GRN<<"COMPLETADO"<<RST
                   << DIM<<"  (hace "<<segsDesdeEvento<<"s  --  pantalla fija "
                   <<(DISPLAY_HOLD_MS/1000 - segsDesdeEvento)<<"s mas)"<<RST;
                estadoDisplay = ss.str();
            } else {
                ostringstream ss;
                ss << GRY<<"COMPLETADO"<<RST
                   << DIM<<"  (hace "<<segsDesdeEvento<<"s)"<<RST;
                estadoDisplay = ss.str();
            }

            cout<<GRY<<"  "<<pad("CAMPO",30)<<pad("HEX",14)<<"VALOR"<<RST<<"\n";
            sep();
            string dispNom=x.nombre;
            if((int)dispNom.size()>45) dispNom=dispNom.substr((int)dispNom.size()-45);
            cout<<"  "<<pad("Archivo",30)<<BOLD<<WHT<<pad("0x--",14)<<RST
                <<dispNom<<"\n";
            cout<<"  "<<pad("Extension",30)<<BOLD<<WHT<<pad("0x--",14)<<RST
                <<YEL<<x.extension<<RST<<"\n";
            cout<<"  "<<pad("Operacion",30)<<BOLD<<WHT<<pad("0x--",14)<<RST
                <<opColor<<"\n";
            {
                ostringstream ts;
                ts<<x.tamBytes<<" bytes  ("
                  <<fixed<<setprecision(2)<<x.tamBytes/1024.0<<" KB)";
                row("Tamano",hx(x.tamBytes,10),x.tamBytes>0?ts.str():"0 (eliminado)");
            }
            row("LBA estimado",      hx(x.lbaEstimado,10),to_string(x.lbaEstimado)+" sector");
            row("Addr. byte en disco",hx(x.lbaEstimado*(unsigned long long)diskBPS,12),
                to_string(x.lbaEstimado*(unsigned long long)diskBPS)+" bytes");
            row("Sectores afectados", hx(x.sectores,8),  to_string(x.sectores)+" sectores");
            row("Bytes de I/O",       hx(x.sectores*(unsigned long long)diskBPS,10),
                to_string(x.sectores*(unsigned long long)diskBPS)+" bytes");
            {
                ostringstream vs;
                vs<<fixed<<setprecision(1)<<x.velMBs<<" MB/s  (estimado interfaz "<<diskIface<<")";
                row("Velocidad transferencia",hx((unsigned long long)x.velMBs,4),vs.str());
            }
            {
                ostringstream ds;
                ds<<fixed<<setprecision(2)<<x.durMs<<" ms";
                row("Duracion estimada",hx((unsigned long long)x.durMs,6),ds.str());
            }
            row("Timestamp",          "0x--",x.timestamp);
            cout<<"  "<<pad("Estado xfer",30)
                <<BOLD<<WHT<<pad(hxb(x.completo),14)<<RST
                <<estadoDisplay<<"\n";
            cout<<"  Progreso: "<<progBarra
                <<fixed<<setprecision(1)<<" "<<progPct<<"%\n";

            // Contador de tiempo en pantalla
            {
                ostringstream tv;
                tv << "  "<<DIM<<"Pantalla fija: "
                   << segsDesdeEvento << "s transcurridos";
                if(eventoReciente){
                    tv <<" / "<<DISPLAY_HOLD_MS/1000<<"s maximos"
                       <<"  (refresca cada "<<REFRESH_INTERVAL_MS/1000<<"s)";
                } else {
                    tv <<" -- mostrando ultimo evento conocido";
                }
                cout<<tv.str()<<RST<<"\n";
            }

            unsigned long long irqCount=(x.sectores>0)?x.sectores:1;
            row("IRQ 14 disparadas est.",hx(irqCount,6),
                to_string(irqCount)+" interrupciones  (1 por sector DMA)");

            // ─── SECCION ECC ──────────────────────────────────────
            seccionECC(x, diskBPS);
        }

        // ─── HISTORIAL DE ARCHIVOS ─────────────────────────────────
        cout<<"\n"<<BOLD<<MGN<<"  \u2550\u2550 HISTORIAL  (ultimos "
            <<min((int)histArchivos.size(),12)<<" eventos)"<<RST<<"\n";
        sep('=',80);
        cout<<GRY<<"  "
            <<pad("HORA",14)<<pad("OP",14)<<pad("EXT",8)
            <<pad("BYTES",14)<<pad("LBA",16)<<"ARCHIVO"<<RST<<"\n";
        sep();
        int maxH=12;
        for(int hi=0;hi<(int)histArchivos.size()&&hi<maxH;hi++){
            auto& h=histArchivos[hi];
            string opC;
            if(h.operacion=="CREADO")          opC=GRN+pad(h.operacion,14)+RST;
            else if(h.operacion=="ELIMINADO")  opC=RED+pad(h.operacion,14)+RST;
            else if(h.operacion.find("RENOMBRADO")!=string::npos)
                                               opC=YEL+pad(h.operacion,14)+RST;
            else                               opC=CYN+pad(h.operacion,14)+RST;
            string nom=h.nombre;
            if((int)nom.size()>28) nom=nom.substr((int)nom.size()-28);
            cout<<"  "
                <<pad(h.timestamp,14)
                <<opC
                <<YEL<<pad(h.extension,8)<<RST
                <<pad(to_string(h.tamBytes),14)
                <<GRY<<pad(hx(h.lbaEstimado,10),16)<<RST
                <<nom<<"\n";
        }
        if(histArchivos.empty()){
            cout<<DIM<<"  (sin eventos aun -- crea o elimina un archivo en C:\\)\n"<<RST;
        }

        header("ESTADO  (reg. 0x1F7)");
        row("Status Register",    "0x50","BSY=0  DRDY=1  DRQ=0  ERR=0");
        row("BSY  bit7  Ocupado", hxb(dmaActivo),
            dmaActivo?YEL+"SI  (xfer activa)"+RST:string("NO  controlador libre"));
        row("DRDY bit6  Listo",   "0x01",GRN+"dispositivo listo"+RST);
        row("DRQ  bit3  Data Req",hxb(dmaActivo),
            dmaActivo?GRN+"SI  (datos en buffer)"+RST:string("NO"));
        row("ERR  bit0  Error",   "0x00","sin error");

        header("COMANDO / CONTROL  (reg. 0x1F7 / 0x3F6)");
        row("Leer sector",       "0x20","READ SECTORS  PIO");
        row("Escribir sector",   "0x30","WRITE SECTORS  PIO");
        row("Iniciar xfer DMA",  "0xC8","READ DMA  Bus Master");
        row("Resetear disco",    "0x04","SRST bit2  (reg. 0x3F6)");
        row("Modo xfer activo",  "0x06","UDMA mode 6  UDMA/133");
        row("Interrupciones",    "0x00","nIEN=0  IRQ 14 habilitada");

        seccionIRQ("INTERRUPCIONES  --  IRQ 14 / 15",{
            {"IRQ 14","0x76","Lectura ATA completada",       true},
            {"IRQ 14","0x76","Escritura ATA completada",     deltaLibreKB<0||hayXfer},
            {"IRQ 14","0x76","Error de sector  (ERR=1)",     false},
            {"IRQ 14","0x76","Disco listo  (DRDY=1)",        true},
            {"IRQ 14","0x76","DMA Bus Master completo",      dmaPhase==3},
            {"IRQ 14","0x76","Archivo detectado  (RDC)",     hayXfer&&!xferActual.completo},
            {"IRQ 15","0x77","Canal secundario listo",       false},
            {"IRQ 15","0x77","Error canal secundario",       false},
        });

        cout<<"\n"<<BOLD<<WHT<<"  DMA  --  ACCESO DIRECTO A MEMORIA  (Bus Master SATA/ATA)"<<RST<<"\n";
        sep();
        cout<<GRY<<"  "<<pad("CAMPO",30)<<pad("HEX",14)<<"VALOR"<<RST<<"\n";
        sep();
        row("Fase actual",            hx(dmaPhase,2),          dmaFaseStr);
        row("Canal DMA",              "0x--",                   dmaCanalStr);
        row("Modo transferencia",     "0x--",                   dmaModoStr);
        row("Archivo en xfer",        "0x--",
            hayXfer?xferActual.nombre.substr(
                min((size_t)0,xferActual.nombre.size()>40?xferActual.nombre.size()-40:(size_t)0))
                   :"(ninguno)");
        row("Dir. base LBA (bytes)",  hx(dmaBaseAddr,12),       to_string(dmaBaseAddr)+" bytes");
        row("Sectores transferidos",  hx(dmaSectores,8),        to_string(dmaSectores)+" sectores");
        row("Bytes transferidos",     hx(dmaTotalBytes,10),     to_string(dmaTotalBytes)+" bytes");
        row("Tamano sector",          hx((unsigned long long)diskBPS,4),
            to_string(diskBPS)+" bytes/sector");
        row("Transferencia activa",   hxb(dmaActivo&&hayXfer),
            (dmaActivo&&hayXfer)?GRN+"SI  -- datos fluyendo"+RST:string("NO"));
        row("Error DMA",              "0x00",                   "sin error");
        cout<<"  "<<DIM
            <<"Flujo: CPU escribe LBA (0x1F3-0x1F6) -> cmd 0xC8 ->\n"
            <<"        DMA lee/escribe sector -> verifica ECC -> copia a RAM -> IRQ 14\n";
        if(hayXfer){
            cout<<"  Archivo: "<<GRN<<xferActual.nombre<<RST<<DIM
                <<"  | "<<xferActual.tamBytes<<" bytes"
                <<"  | "<<dmaSectores<<" sec"
                <<"  | "<<fixed<<setprecision(1)<<xferActual.velMBs<<" MB/s\n";
        }
        cout<<"  "<<RST;

        sep('=',80);
    }

    if(rdcOk){
        CloseHandle(ov.hEvent);
        CloseHandle(hDir);
    }
}

// ══════════════════════════════════════════════════════════════
//  LANZADOR
// ══════════════════════════════════════════════════════════════
void lanzar() {
    enableColors();
    SetConsoleOutputCP(65001);

    char exePath[MAX_PATH];
    GetModuleFileNameA(NULL,exePath,MAX_PATH);
    string exe="\""+string(exePath)+"\"";

    struct Ventana { string arg; string titulo; };
    Ventana ventanas[]={
        {"mouse",   "MOUSE -- Controlador"},
        {"teclado", "TECLADO -- Controlador"},
        {"monitor", "MONITOR -- GPU + Display + Ventanas"},
        {"disco",   "DISCO DURO -- Controlador + Archivos + DMA"},
    };

    sep('=',80);
    cout<<BOLD<<WHT<<"  REGISTROS DE CONTROLADORES E/S\n"<<RST;
    sep('=',80);
    cout<<"\n  Abriendo 4 ventanas...\n\n";

    for(auto& v:ventanas){
        string cmd="/C \"title "+v.titulo
            +" && mode con cols=84 lines=65"
            +" && "+exe+" "+v.arg+"\"";
        ShellExecuteA(NULL,"open","cmd",cmd.c_str(),NULL,SW_SHOWNORMAL);
        cout<<"  "<<GRN<<"OK"<<RST<<"  "<<v.titulo<<"\n";
        Sleep(400);
    }
    cout<<"\n  Listo. Puedes cerrar esta ventana.\n";
    Sleep(2500);
}

// ══════════════════════════════════════════════════════════════
//  MAIN
// ══════════════════════════════════════════════════════════════
int main(int argc,char* argv[]){
    enableColors();
    if(argc<2){ lanzar(); return 0; }
    string modo=argv[1];
    if     (modo=="mouse")   runMouse();
    else if(modo=="teclado") runTeclado();
    else if(modo=="monitor") runMonitor();
    else if(modo=="disco")   runDisco();
    else{
        cout<<RED<<"Argumento desconocido: "<<modo<<RST<<"\n";
        return 1;
    }
    return 0;
}
