# Weather and environmental alerts live study

This category contains 10 reviewed candidates. 7 are
currently eligible for the two-cycle qualification. A later 24-hour study is
configured separately and is not started by the qualification command.

| Website | Stable ID | Current status | Qualification URL |
|---|---|---|---|
| NOAA National Hurricane Center | `weather-noaa-nhc` | excluded after pilot | https://www.nhc.noaa.gov/ |
| Environment Canada Alerts | `weather-environment-canada` | excluded after pilot | https://weather.gc.ca/mainmenu/alert_menu_e.html |
| UK Met Office Warnings | `weather-uk-met-office` | eligible for qualification | https://weather.metoffice.gov.uk/warnings-and-advice/uk-warnings |
| Met Éireann Warnings | `weather-met-eireann` | eligible for qualification | https://www.met.ie/warnings-today.html |
| MetService New Zealand Warnings | `weather-metservice-nz` | excluded after pilot | https://www.metservice.com/warnings/home |
| KNMI Netherlands Warnings | `weather-knmi-nl` | eligible for qualification | https://www.knmi.nl/nederland-nu/weer/waarschuwingen/utrecht |
| AEMET Spain Warnings | `weather-aemet-es` | eligible for qualification | https://www.aemet.es/en/eltiempo/prediccion/avisos |
| Météo-France Vigilance | `weather-meteofrance` | eligible for qualification | https://vigilance.meteofrance.fr/fr |
| Finnish Meteorological Institute Warnings | `weather-fmi-finland` | eligible for qualification | https://en.ilmatieteenlaitos.fi/warnings |
| Meteorological Service Singapore Heavy Rain Warning | `weather-mss-singapore` | eligible for qualification | https://www.weather.gov.sg/warning-heavy-rain/ |

Exact hosts, discovery limits, template mappings, and exclusion reasons are in
[`input/sites.json`](input/sites.json). Completed evidence appears under
`runs/`; an empty `runs/` folder means that no public run has been released.
