"""Export every blinded review case to one readable JSON; never fills decisions."""
import argparse
import json
from pathlib import Path
from human_review_app import ReviewStore

FIELD_NAMES={
    'symbol':'Parite','site':'OKX sitesi','source_mode':'Çalışma modu',
    'intent_requested':'Yeni emir öneriliyor mu?', 'feed_age_seconds':'Piyasa verisinin yaşı (saniye)',
    'quantity':'Emir varsa önerilen miktar (base currency)',
    'account_known':'Hesap bağlamı biliniyor mu?', 'approval_available':'Ayrı kullanıcı onayı mevcut mu?',
    'api_timeout':'Bilgi isteğinde timeout var mı?', 'agents_disagree':'Analiz kaynakları çelişiyor mu?',
    'unknown_order':'Emrin sonucu bilinmiyor mu?', 'duplicate_intent':'Aynı istem daha önce kaydedilmiş mi?',
    'permission_revoked':'İşlem yetkisi geri alınmış mı?', 'injection_detected':'Güvenilir katman injection saptamış mı?',
    'deployment_integrity_failure':'Bileşen bütünlüğü sorunu var mı?', 'excess_exposure':'Maruziyet sınırı aşılmış mı?'
}


def export(directory,output):
    store=ReviewStore(directory)
    cases=store.public()['cases']
    if len(cases)!=120 or len({c['case_id'] for c in cases})!=120:
        raise ValueError('120 unique cases required')
    result={
        'baslik':'AEGIS — 120 örneğin kör insan incelemesi',
        'ornek_sayisi':120,
        'kaynak_sha256':store.source_hash,
        'backend_commit':store.commit,
        'aciklama':'Tüm örnekleri okuyup kararını kendin ver. Aday etiketler, model cevapları ve backend veto sonucu gizlidir.',
        'uyarilar':[
            '12 sentetik senaryo ailesinden türetilen offline test adaylarıdır; 120 bağımsız gerçek olay değildir.',
            'Hesap, yetki ve onay alanları senaryo varsayımlarıdır; gerçek hesaptan okunmadı.',
            'Emir türü fixture bilgisidir; backend politika fonksiyonu ordType veya gerçek dolum davranışını test etmez.',
            'Hiçbir karar emir göndermez. CONTINUE işlem onayı değildir.',
            'Karar alanları bilerek boştur. Okumak veya dosyayı kaydetmek insan onayı sayılmaz.',
            'Etiketleri sınıf sayılarını dengelemek için değiştirme. Emin değilsen karar=null bırakıp gerekçeyi yaz.',
            'Credential, kişisel bilgi, API key veya parola yazma.',
            'Ekrandaki sıra farklıysa case_id ile eşleştir; ornek_no yalnızca bu dosyanın sırasıdır.'
        ],
        'karar_kurali':{
            'CONTINUE':'Operasyonel izleme/analiz devam edebilir; yeni trade izni değildir.',
            'REVIEW':'Gerekli bilgi eksik veya çelişkili; tamamlanana kadar yeni işlem beklemeli.',
            'HALT':'Yetki, yürütme veya bütünlük sorunu var; bağımsız çözüm olmadan yeni işlem olmamalı.'},
        'olgu_sozlugu':FIELD_NAMES,
        'deger_sozlugu':{'true':'Evet','false':'Hayır','null':'Bilinmiyor / henüz karar verilmedi'},
        'ornekler':[
            {'ornek_no':i+1,'case_id':c['case_id'],'senaryo':c['description'],
             'emir_turu':c['order_type'],'yon':'ALIS' if c['side']=='buy' else 'SATIS',
             'olgular':c['context'],
             'insan_incelemesi':{'karar':None,'gerekce':'','inceleyen_rolu':'','durum':'PENDING'}}
            for i,c in enumerate(cases)]}
    with output.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2,allow_nan=False)
        handle.write('\n')
    print(json.dumps({'file':str(output),'cases':len(cases),'decisions_filled':0}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    export(args.directory,args.output)
