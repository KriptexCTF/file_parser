# file_parser
Recursive search for matches in files and archives

### python log_searcher.py --path /backups -s "ERROR" -f "*.log,*.gz,*.zip" -r -e

### python log_searcher.py --path ./logs -s "username" -f "*.log,*.txt" -r -e -i


#### Help
```
usage: main.py [-h] --path PATH -s SEARCH [-f FILE_PATTERNS] [-r] [-e] [-v] [-i] [--no-color] [--max-depth MAX_DEPTH]

Поиск строк в логах и архивах

optional arguments:
  -h, --help            show this help message and exit
  --path PATH           Директория для поиска
  -s SEARCH, --search SEARCH
                        Строка или регулярное выражение для поиска
  -f FILE_PATTERNS, --file-patterns FILE_PATTERNS
                        Шаблоны файлов для поиска (через запятую)
  -r, --recursive       Рекурсивный поиск в поддиректориях
  -e, --extract-archives
                        Распаковывать и искать в архивах (включая вложенные)
  -v, --verbose         Подробный вывод
  -i, --ignore-case     Игнорировать регистр
  --no-color            Отключить цветной вывод
  --max-depth MAX_DEPTH
                        Максимальная глубина рекурсии в архивах (по умолчанию: 5)
```
