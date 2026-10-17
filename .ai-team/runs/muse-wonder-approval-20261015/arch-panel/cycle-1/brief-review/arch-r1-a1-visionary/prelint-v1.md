JD-01 | brief начинается байтами prompt-visionary.txt + пустая строка; sha256 префикса 63c5304b9e9385ae | pass | 
HY-01 | первая строка judge-prompt — HEARTBEAT только для не-стрим слотов (hermes -z); транспорт droid стримит (-o stream-json) | pass | N/A для стримящего слота
SK-A-02 | обёртка ARTIFACT пакета sha256=ebfa59a9869c9deb == receipt.packet_sha256 == sha256 файла | pass | 
SK-A-12 | seat_slot gemini-4-argon-high != architect_slot muse-wonder-full-1.0 | pass | 
D9-WRAP | тела всех обёрток ARTIFACT равны источникам по cmp и sha256 | pass | []
HY-03 | плейсхолдеры закрытого списка вне обёрток | fail | ['<K>', '<N>']
