#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import argparse
import gzip
import bz2
import zipfile
import tarfile
import fnmatch
import tempfile
import magic
from pathlib import Path
from typing import List, Optional, Pattern, Union, IO, Any

class LogSearcher:
	def __init__(self, verbose: bool = False, color: bool = True):
		self.verbose = verbose
		self.color = color
		self.processed_files = 0
		self.found_matches = 0
		
	def log(self, message: str):
		if self.verbose:
			print(f"[DEBUG] {message}")
	
	def colorize_path(self, text: str) -> str:
		if not self.color:
			return text
		# Оранжевый цвет: \033[38;5;208m
		return f"\033[38;5;208m{text}\033[0m"
	
	def highlight_match(self, text: str, match: re.Match) -> str:
		if not self.color:
			return text
		start, end = match.span()
		matched_text = text[start:end]
		# Зеленый цвет для подсветки: \033[92m
		highlighted = f"{text[:start]}\033[92m{matched_text}\033[0m{text[end:]}"
		return highlighted
	
	def print_match(self, file_path: str, line_num: int, line_content: str):
		if self.color:
			colored_prefix = self.colorize_path(f"{file_path}:{line_num}:")
			print(f"{colored_prefix} {line_content}")
		else:
			print(f"{file_path}:{line_num}: {line_content}")

	def detect_archive_type(self, file_path: Path) -> str:
		try:
			with open(file_path, 'rb') as f:
				header = f.read(1024)  # Читаем первые 1024 байта
			if header.startswith(b'PK'):  # ZIP
				return 'zip'
			elif header.startswith(b'\x1f\x8b'):  # GZIP
				return 'gzip'
			elif header.startswith(b'BZh'):  # BZIP2
				return 'bzip2'
			elif header.startswith(b'\x1f\x9d'):  # COMPRESS
				return 'compress'
			elif header.startswith(b'\x1f\xa0'):  # COMPRESS
				return 'compress'
			elif b'ustar' in header[:512]:  # TAR
				return 'tar'
			else:
				# Пытаемся определить по расширению как fallback
				if file_path.suffix.lower() in ['.zip']:
					return 'zip'
				elif file_path.suffix.lower() in ['.gz', '.tgz']:
					return 'gzip'
				elif file_path.suffix.lower() in ['.bz2', '.tbz2']:
					return 'bzip2'
				elif file_path.suffix.lower() in ['.tar']:
					return 'tar'
				elif any(file_path.name.lower().endswith(ext) for ext in ['.tar.gz', '.tgz']):
					return 'gzip'
				elif any(file_path.name.lower().endswith(ext) for ext in ['.tar.bz2', '.tbz2']):
					return 'bzip2'
		except Exception as e:
			self.log(f"Ошибка при определении типа архива {file_path}: {e}")
		return 'unknown'

	def search_in_file(self, file_path: Path, search_pattern: Pattern, 
					  extract_archives: bool, max_depth: int = 5, current_depth: int = 0) -> bool:
		if current_depth > max_depth:
			self.log(f"Превышена максимальная глубина рекурсии для {file_path}")
			return False
		found = False
		try:
			# Проверяем, является ли файл архивом
			if extract_archives and self.is_archive(file_path):
				self.log(f"Обработка архива (уровень {current_depth}): {file_path}")
				found = self.search_in_archive(file_path, search_pattern, extract_archives, max_depth, current_depth)
			else:
				# Обычный файл
				self.log(f"Поиск в файле: {file_path}")
				found = self.search_in_text_file(file_path, search_pattern)
		except Exception as e:
			print(f"Ошибка при обработке файла {file_path}: {e}")
		return found
	
	def is_archive(self, file_path: Path) -> bool:
		"""Проверяет, является ли файл архивом"""
		archive_extensions = ['.zip', '.tar', '.gz', '.bz2', '.tgz', '.tbz2', '.tar.gz', '.tar.bz2']
		return (file_path.suffix.lower() in archive_extensions or
				any(file_path.name.lower().endswith(ext) for ext in ['.tar.gz', '.tar.bz2']))
	
	def get_tar_mode(self, file_path: Path) -> str:
		"""Определяет режим открытия TAR архива на основе реального типа"""
		archive_type = self.detect_archive_type(file_path)
		if archive_type == 'gzip':
			return 'r:gz'
		elif archive_type == 'bzip2':
			return 'r:bz2'
		elif archive_type == 'tar':
			return 'r'
		else:
			# Fallback по расширению
			if any(file_path.name.lower().endswith(ext) for ext in ['.tar.gz', '.tgz']):
				return 'r:gz'
			elif any(file_path.name.lower().endswith(ext) for ext in ['.tar.bz2', '.tbz2']):
				return 'r:bz2'
			else:
				return 'r'  # Пробуем обычный TAR

	def search_in_text_file(self, file_path: Path, search_pattern: Pattern) -> bool:
		"""Поиск в текстовом файле"""
		found = False
		self.processed_files += 1
		try:
			# Определяем способ открытия файла в зависимости от расширения
			if file_path.suffix.lower() == '.gz':
				opener = gzip.open
				mode = 'rt'
			elif file_path.suffix.lower() == '.bz2':
				opener = bz2.open
				mode = 'rt'
			else:
				opener = open
				mode = 'r'
			with opener(file_path, mode, encoding='utf-8', errors='ignore') as file:
				for line_num, line in enumerate(file, 1):
					match = search_pattern.search(line)
					if match:
						# Подсвечиваем найденное совпадение
						highlighted_line = self.highlight_match(line.rstrip('\n'), match)
						self.print_match(str(file_path), line_num, highlighted_line)
						found = True
						self.found_matches += 1
		except UnicodeDecodeError:
			# Пропускаем бинарные файлы
			self.log(f"Пропуск бинарного файла: {file_path}")
		except Exception as e:
			print(f"Ошибка при чтении файла {file_path}: {e}")
		return found
	
	def search_in_archive(self, archive_path: Path, search_pattern: Pattern, 
						 extract_archives: bool, max_depth: int, current_depth: int) -> bool:
		"""Поиск в архиве"""
		found = False
		try:
			archive_type = self.detect_archive_type(archive_path)
			self.log(f"Тип архива {archive_path}: {archive_type}")
			if archive_type == 'zip':
				found = self.search_in_zip(archive_path, search_pattern, extract_archives, max_depth, current_depth)
			elif archive_type in ['gzip', 'bzip2', 'tar']:
				found = self.search_in_tar(archive_path, search_pattern, extract_archives, max_depth, current_depth)
			else:
				# Пробуем по расширению как fallback
				if archive_path.suffix.lower() in ['.zip']:
					found = self.search_in_zip(archive_path, search_pattern, extract_archives, max_depth, current_depth)
				elif any(archive_path.name.lower().endswith(ext) for ext in ['.tar', '.tar.gz', '.tar.bz2', '.tgz', '.tbz2']):
					found = self.search_in_tar(archive_path, search_pattern, extract_archives, max_depth, current_depth)
		except Exception as e:
			print(f"Ошибка при обработке архива {archive_path}: {e}")
		return found
	
	def search_in_zip(self, zip_path: Path, search_pattern: Pattern, 
					 extract_archives: bool, max_depth: int, current_depth: int) -> bool:
		"""Поиск в ZIP архиве с поддержкой вложенных архивов"""
		found = False
		try:
			with zipfile.ZipFile(zip_path, 'r') as zip_ref:
				for file_info in zip_ref.infolist():
					if not file_info.is_dir():
						file_extension = Path(file_info.filename).suffix.lower()
						file_name = file_info.filename.lower()
						# Если это вложенный архив и разрешена распаковка
						if extract_archives and (file_extension in ['.zip', '.tar', '.gz', '.bz2', '.tgz', '.tbz2'] or 
											   any(file_name.endswith(ext) for ext in ['.tar.gz', '.tar.bz2'])):
							# Обрабатываем вложенный архив
							with zip_ref.open(file_info) as nested_file:
								# Создаем временный файл для обработки
								with tempfile.NamedTemporaryFile(delete=True, suffix=file_extension) as temp_file:
									temp_file.write(nested_file.read())
									temp_file.flush()
									# Рекурсивно обрабатываем вложенный архив
									nested_found = self.search_in_file(
										Path(temp_file.name), search_pattern, 
										extract_archives, max_depth, current_depth + 1
									)
									found = found or nested_found
						else:
							# Обычный текстовый файл
							with zip_ref.open(file_info) as file:
								try:
									content = file.read().decode('utf-8', errors='ignore')
									for line_num, line in enumerate(content.split('\n'), 1):
										match = search_pattern.search(line)
										if match:
											# Подсвечиваем найденное совпадение
											highlighted_line = self.highlight_match(line.rstrip('\n'), match)
											full_path = f"{zip_path}/{file_info.filename}"
											self.print_match(full_path, line_num, highlighted_line)
											found = True
											self.found_matches += 1
								except Exception as e:
									self.log(f"Ошибка при чтении файла {file_info.filename}: {e}")
		except Exception as e:
			print(f"Ошибка при обработке ZIP архива {zip_path}: {e}")
		return found

	def search_in_tar(self, tar_path: Path, search_pattern: Pattern, 
					 extract_archives: bool, max_depth: int, current_depth: int) -> bool:
		"""Поиск в TAR архиве с поддержкой вложенных архивов"""
		found = False
		try:
			mode = self.get_tar_mode(tar_path)
			self.log(f"Открытие TAR архива {tar_path} в режиме {mode}")
			# Пробуем разные режимы открытия если основной не работает
			modes_to_try = [mode]
			if mode == 'r:gz':
				modes_to_try.extend(['r:bz2', 'r'])
			elif mode == 'r:bz2':
				modes_to_try.extend(['r:gz', 'r'])
			else:
				modes_to_try.extend(['r:gz', 'r:bz2'])
			for try_mode in modes_to_try:
				try:
					with tarfile.open(tar_path, try_mode) as tar:
						self.log(f"Успешно открыт архив {tar_path} в режиме {try_mode}")
						for member in tar:
							if member.isfile():
								file_name = member.name.lower()
								file_extension = Path(member.name).suffix.lower()
								# Если это вложенный архив и разрешена распаковка
								if extract_archives and (file_extension in ['.zip', '.tar', '.gz', '.bz2', '.tgz', '.tbz2'] or 
													   any(file_name.endswith(ext) for ext in ['.tar.gz', '.tar.bz2'])):
									# Обрабатываем вложенный архив
									file_obj = tar.extractfile(member)
									if file_obj:
										with tempfile.NamedTemporaryFile(delete=True, suffix=file_extension) as temp_file:
											temp_file.write(file_obj.read())
											temp_file.flush()
											# Рекурсивно обрабатываем вложенный архив
											nested_found = self.search_in_file(
												Path(temp_file.name), search_pattern, 
												extract_archives, max_depth, current_depth + 1
											)
											found = found or nested_found
								else:
									# Обычный текстовый файл
									file_obj = tar.extractfile(member)
									if file_obj:
										try:
											content = file_obj.read().decode('utf-8', errors='ignore')
											for line_num, line in enumerate(content.split('\n'), 1):
												match = search_pattern.search(line)
												if match:
													# Подсвечиваем найденное совпадение
													highlighted_line = self.highlight_match(line.rstrip('\n'), match)
													full_path = f"{tar_path}/{member.name}"
													self.print_match(full_path, line_num, highlighted_line)
													found = True
													self.found_matches += 1
										except Exception as e:
											self.log(f"Ошибка при чтении файла {member.name}: {e}")
						break  # Успешно открыли, выходим из цикла
				except (tarfile.ReadError, OSError) as e:
					self.log(f"Не удалось открыть {tar_path} в режиме {try_mode}: {e}")
					continue
			else:
				print(f"Не удалось открыть архив {tar_path} ни в одном из режимов")
							
		except Exception as e:
			print(f"Ошибка при обработке TAR архива {tar_path}: {e}")
		return found

	def search_directory(self, directory: Path, search_pattern: Pattern, 
						file_patterns: List[str], recursive: bool, 
						extract_archives: bool, max_depth: int = 10):
		"""Рекурсивный поиск в директории"""
		try:
			for item in directory.iterdir():
				if item.is_file():
					# Проверяем соответствие шаблону файлов
					if any(fnmatch.fnmatch(item.name.lower(), pattern.lower()) 
						  for pattern in file_patterns):
						self.search_in_file(item, search_pattern, extract_archives, max_depth)
				elif item.is_dir() and recursive:
					self.search_directory(item, search_pattern, file_patterns, 
										 recursive, extract_archives, max_depth)
		except PermissionError:
			print(f"Нет доступа к директории: {directory}")
		except Exception as e:
			print(f"Ошибка при обработке директории {directory}: {e}")

def main():
	parser = argparse.ArgumentParser(description='Поиск строк в логах и архивах')
	parser.add_argument('--path', type=str, required=True, 
					   help='Директория для поиска')
	parser.add_argument('-s', '--search', type=str, required=True,
					   help='Строка или регулярное выражение для поиска')
	parser.add_argument('-f', '--file-patterns', type=str, default='*.log,*.txt,*.lgf,*.lgp,*.lgx',
					   help='Шаблоны файлов для поиска (через запятую)')
	parser.add_argument('-r', '--recursive', action='store_true',
					   help='Рекурсивный поиск в поддиректориях')
	parser.add_argument('-e', '--extract-archives', action='store_true',
					   help='Распаковывать и искать в архивах (включая вложенные)')
	parser.add_argument('-v', '--verbose', action='store_true',
					   help='Подробный вывод')
	parser.add_argument('-i', '--ignore-case', action='store_true',
					   help='Игнорировать регистр')
	parser.add_argument('--no-color', action='store_true',
					   help='Отключить цветной вывод')
	parser.add_argument('--max-depth', type=int, default=5,
					   help='Максимальная глубина рекурсии в архивах (по умолчанию: 5)')
	
	args = parser.parse_args()
	
	# Проверяем существование директории
	search_path = Path(args.path)
	if not search_path.exists():
		print(f"Директория {args.path} не существует!")
		sys.exit(1)
	
	# Компилируем регулярное выражение
	try:
		flags = re.IGNORECASE if args.ignore_case else 0
		search_pattern = re.compile(args.search, flags)
	except re.error as e:
		print(f"Ошибка в регулярном выражении: {e}")
		sys.exit(1)
	
	# Разбираем шаблоны файлов
	file_patterns = [pattern.strip() for pattern in args.file_patterns.split(',')]
	
	# Создаем и запускаем поисковик
	searcher = LogSearcher(verbose=args.verbose, color=not args.no_color)
	
	print(f"Поиск '{args.search}' в {args.path}")
	if args.recursive:
		print("Режим: рекурсивный")
	if args.extract_archives:
		print(f"Режим: с распаковкой архивов (макс. глубина: {args.max_depth})")
	if not args.no_color:
		print("Цветной вывод: включен")
	print("-" * 50)
	
	if search_path.is_file():
		# Поиск в одном файле
		searcher.search_in_file(search_path, search_pattern, args.extract_archives, args.max_depth)
	else:
		# Поиск в директории
		searcher.search_directory(search_path, search_pattern, file_patterns, 
								 args.recursive, args.extract_archives, args.max_depth)
	
	print("-" * 50)
	print(f"Обработано файлов: {searcher.processed_files}")
	print(f"Найдено совпадений: {searcher.found_matches}")

if __name__ == "__main__":
	main()
