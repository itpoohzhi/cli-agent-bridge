JD-01 | brief начинается байтами prompt-realist.txt + пустая строка | pass | 
HY-01 | HEARTBEAT только для не-стрим слотов; транспорт стримит (-o stream-json) | pass | N/A
SK-A-02 | обёртка пакета sha256=9ddc18254368aa86 == receipt.packet_sha256 | pass | 
SK-A-12 | seat_slot gemini-4-argon-high != architect_slot gpt-6.1-sol-high | pass | 
D9-WRAP | тела всех обёрток ARTIFACT равны источникам по cmp и sha256 | pass | []
HY-03 | плейсхолдеры закрытого списка вне обёрток | pass | []
