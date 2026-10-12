# S.T.A.L.K.E.R. × Portal 2

Мод для **S.T.A.L.K.E.R.: Тень Чернобыля** на движке [OGSR Engine](https://github.com/OGSR/OGSR-Engine): переносит в Зону
механику Portal 2.

- **Ботинки длинного прыжка** (артефакт на пояс): гасят урон от падения.
- **Портальная пушка** с моделью и звуками Portal 2: синий и оранжевый портал, вид сквозь портал (второй проход
  рендера), порталы ложатся по углу поверхности.
- **Через порталы проходит всё**: игрок (с сохранением скорости), пули, ракеты РПГ, гранаты (с «засасыванием» в
  портал, как в Portal 2), предметы, NPC, мутанты и трупы. В портал на полу проваливается то, что на нём стоит.

Работа в процессе: полная история решений, факты о движке и грабли описаны в [MODLOG.md](MODLOG.md).

## Что нужно

- S.T.A.L.K.E.R.: Тень Чернобыля (GOG) на OGSR Engine 3.518.
- Исходники OGSR Engine (тег 3.519) и Visual Studio 2022 (C++), Python 3.11.
- **Установленный Portal 2**: его текстуры, звуки и модель пушки конвертируются скриптами локально, со своей копии
  игры. В репозитории нет ни ассетов Portal 2, ни файлов из архивов STALKER.

Пути в скриптах пока зашиты под машину автора (`E:\Games\...`, `E:\github\OGSR-Engine`, `E:\SteamLibrary\...`):
поправь их в начале `tools/*.py` и `tools/build_ogsr.cmd`.

## Сборка

1. Движок: в чекауте OGSR Engine по очереди применить `tools/engine_patches/patch_e1.py` … `patch_e9.py`
   (`python -I tools/engine_patches/patch_eN.py`), собрать `tools\build_ogsr.cmd` и положить `bin_x64\xrEngine.exe`
   в папку игры как `bin_portal\xrEngine.exe` (родной `bin_x64` не трогается). Для MSVC 17.14 движку нужны ещё две
   правки сборки: dependent `static_assert` и quad index buffer без `consteval`.
2. Ассеты Portal 2: `tools/p2_assets.py` (текстуры, звуки), `tools/p2_gun_ogf.py` (модель пушки в OGF),
   `tools/make_icons.py` (иконки инвентаря). Всё пишется в `_gen/` (в git не попадает).
3. Установка в игру: `python -I tools/deploy.py` (делает бэкап, ставит `mod/gamedata` + `_gen/gamedata`, добавляет хуки
   в `bind_stalker.script`). Удаление: `--uninstall`.

Запуск: `bin_portal\xrEngine.exe`.

## Управление

| Клавиша | Действие |
|---|---|
| F8 | выдать портальную пушку (режим разработчика) |
| F6 | выдать ботинки длинного прыжка |
| ЛКМ / ПКМ | синий / оранжевый портал |
| R | закрыть порталы |

## Тесты

`tools/lab.py` запускает игру на отдельном лабораторном профиле с автотестом и пишет видео
(`python -I tools/deploy.py --autotest bar` → `python -I tools/lab.py --engine bin_portal --save bar --record take`).
Сценарии: `boots`, `portals`, `gun`, `bar` (стрельба через порталы), `npc` (NPC и трупы через портал в полу).
