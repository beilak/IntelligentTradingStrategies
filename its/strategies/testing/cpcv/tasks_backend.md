Правки
1 Backend
1.1 Предлагаю оставить в @cpcv.py файле только то что относится к эндпоинту. Все функции для генерации CPCV и формирования отчетов перенести в папку strategies/testing/cpcv/


UI для сервиса strategy-ui (работа с CPCV)
Во вкладке Core Strategy, при выборе модели, справа в разделе Report (переименуем в Testing) было 3 кнопкуи - CPCV, WalkForward, Backtesting. Ты убрал кнопку CPCV и сделал его продолжением этого блока - это не удобно.
Как я вижу этот раздел:
Тут по прежнему 3 кнопки - CPCV, WalkForward, Backtesting
При клике CPCV открывается новое модальное окно на весь экран и там уже идет вся работа с CPCV



UI для сервиса strategy-ui (работа с CPCV)
В настройках CPCV testing не нужно ограничивать Asset limit - я хочу работать со всеми Asset 


UI для сервиса strategy-ui (работа с CPCV)
В настройках CPCV testing хочу указывать настройки размера теста ( test_size=0.33)


UI для сервиса strategy-ui (работа с CPCV)
В настройках CPCV есть галочка Recalculate, она не нужна. Если я кликаю на Run And Save значит это должно быть пересчитана и пересохранена.

[@src](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/ui/strategy-ui/src/) 
[@strategy_backend](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/services/strategy_backend/) 
[@cpcv](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/its/strategies/testing/cpcv/)


UI для сервиса strategy-ui (работа с CPCV)
На графике по CPCV нет данных на по горизонтальной и вертикальной линии (там возможно нанести даты и стомость активов или что то еще что бы дала ясность по графику?)
[@src](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/ui/strategy-ui/src/) 
[@strategy_backend](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/services/strategy_backend/) 
[@cpcv](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/its/strategies/testing/cpcv/)


UI для сервиса strategy-ui (работа с CPCV)
2.6 Таблица с метриками CPCV исключительна на английском языке, метрики возможно перевести на Ru тоже?
[@src](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/ui/strategy-ui/src/) 
[@strategy_backend](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/services/strategy_backend/) 
[@cpcv](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/its/strategies/testing/cpcv/)

 

UI для сервиса strategy-ui (работа с CPCV)
В результатах CPCV так же есть данные по assets которые входили в тест
пример:
"assets": [
     {
       "figi": "TCS10A0JNAB6",
       "ticker": "ABIO",
       "name": "Артген"
     },
     {
       "figi": "BBG002W2FT69",
       "ticker": "ABRD",
       "name": "АбрауДюрсо"
     },
     {
       "figi": "BBG004S68614",
       "ticker": "AFKS",
       "name": "АФК Система"
     },
Хочу кнопку, по нажатию которого откроется модальное окно с этой информацией (хочу видеть этот список)
[@src](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/ui/strategy-ui/src/) 
[@strategy_backend](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/services/strategy_backend/) 
[@cpcv](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/its/strategies/testing/cpcv/)

---

UI для сервиса strategy-ui (работа с CPCV)
UI Модального окна CPCV не очень user-frendly из за того что таблица с метриками слишком длинная. Неободимо что то придумать. слишком много неэффективной области на экране (пустота)
[@src](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/ui/strategy-ui/src/) 
[@strategy_backend](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/services/strategy_backend/) 
[@cpcv](file:///Users/beilakaliev/projects/IntelligentTradingStrategies/its/strategies/testing/cpcv/)
