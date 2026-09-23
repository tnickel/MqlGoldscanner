//+------------------------------------------------------------------+
//| CalendarExport.mq5 — MqlGoldscanner                              |
//|                                                                  |
//| Exportiert den MT5-Wirtschaftskalender (nur LESEND, kein Handel):|
//| Standard: 2 Jahre Historie + 6 Monate Zukunft, Währung USD.      |
//| Kalenderwerte sind laut MQL5-Doku mit 1e6 skaliert und werden    |
//| hier durch 1e6 geteilt.                                          |
//|                                                                  |
//| Ausgabe: goldscanner_calendar.csv im GEMEINSAMEN Dateien-Ordner  |
//| (Common\Files, FILE_COMMON), Semikolon-getrennt, Spalten:        |
//| date;time_iso;event;currency;importance;type;actual;forecast;previous |
//|                                                                  |
//| Installation (einmalig):                                         |
//|  1. Datei nach <Terminal-Datenordner>\MQL5\Scripts\ kopieren     |
//|  2. Im MetaEditor kompilieren (F7)                               |
//|  3. Skript einmal auf ein beliebiges Chart ziehen                |
//| Danck: wöchentlich wiederholen (z. B. nach dem COT-Release).     |
//+------------------------------------------------------------------+
#property copyright "MqlGoldscanner"
#property version   "1.00"
#property script_show_inputs
#property description "Exportiert USD-Wirtschaftskalender nach CSV (read-only)"

input int    JahreZurueck = 2;     // Historie in Jahren
input int    MonateVor    = 6;     // Zukunft in Monaten
input string Waehrung     = "USD"; // Kalender-Währung

//+------------------------------------------------------------------+
string IsoDatum(const datetime t)
  {
   MqlDateTime strk;
   TimeToStruct(t, strk);
   return StringFormat("%04d-%02d-%02d", strk.year, strk.mon, strk.day);
  }

string IsoZeit(const datetime t)
  {
   MqlDateTime strk;
   TimeToStruct(t, strk);
   return StringFormat("%04d-%02d-%02d %02d:%02d", strk.year, strk.mon, strk.day,
                       strk.hour, strk.min);
  }

//+------------------------------------------------------------------+
void OnStart()
  {
   datetime von = TimeCurrent() - (datetime)(JahreZurueck * 365 * 86400);
   datetime bis = TimeCurrent() + (datetime)(MonateVor * 31 * 86400);

   MqlCalendarValue werte[];
   ResetLastError();
   int anzahl = CalendarValueHistory(werte, von, bis, NULL, Waehrung);
   if(anzahl <= 0)
     {
      PrintFormat("CalendarExport: keine Werte (%d), Fehler=%d", anzahl, GetLastError());
      return;
     }

   int handle = FileOpen("goldscanner_calendar.csv",
                         FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ';');
   if(handle == INVALID_HANDLE)
     {
      PrintFormat("CalendarExport: Datei nicht schreibbar, Fehler=%d", GetLastError());
      return;
     }

   FileWrite(handle, "date;time_iso;event;currency;importance;type;actual;forecast;previous");

   MqlCalendarEvent ereignis;
   for(int i = 0; i < anzahl; i++)
     {
      if(!CalendarEventById(werte[i].event_id, ereignis))
         continue;

      double actual   = (werte[i].HasActualValue()   ? werte[i].actual_value   / 1e6 : 0.0);
      double forecast = (werte[i].HasForecastValue() ? werte[i].forecast_value / 1e6 : 0.0);
      double previous = (werte[i].HasPreviousValue() ? werte[i].previous_value / 1e6 : 0.0);

      FileWrite(handle,
                IsoDatum(werte[i].time),
                IsoZeit(werte[i].time),                    // MT5-Serverzeit
                ereignis.name,
                Waehrung,
                IntegerToString((int)ereignis.importance), // 0 none/1 low/2 moderate/3 high
                IntegerToString((int)ereignis.type),
                DoubleToString(actual,   6),
                DoubleToString(forecast, 6),
                DoubleToString(previous, 6));
     }
   FileClose(handle);
   PrintFormat("CalendarExport: %d Zeilen nach Common\\Files\\goldscanner_calendar.csv",
               anzahl);
  }
//+------------------------------------------------------------------+
