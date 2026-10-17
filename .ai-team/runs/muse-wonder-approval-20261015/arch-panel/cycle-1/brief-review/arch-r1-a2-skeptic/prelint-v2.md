JD-01 | brief начинается байтами prompt-skeptic.txt + пустая строка | pass | 
HY-01 | HEARTBEAT только для не-стрим слотов; транспорт стримит (-o stream-json) | pass | N/A
SK-A-02 | обёртка пакета sha256=c1fc50b0f918b7ef == receipt.packet_sha256 | pass | 
SK-A-12 | seat_slot gemini-4-argon-high != architect_slot muse-wonder-full-1.0 | pass | 
D9-WRAP | тела всех обёрток ARTIFACT равны источникам по cmp и sha256 | pass | []
HY-03 | плейсхолдеры закрытого списка вне обёрток | pass | []
