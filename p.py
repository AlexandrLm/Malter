import json

# Имена входного и выходного файлов
input_filename = 'result.json'
output_filename = 'output.json'

def parse_chat_history(input_file, output_file):
    """
    Парсит JSON-файл с историей чата, извлекая только отправителя и текст сообщения.
    """
    
    # Список для хранения очищенных сообщений
    cleaned_messages = []

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Ошибка: Файл '{input_file}' не найден.")
        return
    except json.JSONDecodeError:
        print(f"Ошибка: Не удалось прочитать JSON из файла '{input_file}'. Проверьте его формат.")
        return

    # Проверяем, есть ли ключ 'messages' в JSON
    if 'messages' not in data:
        print("Ошибка: В JSON-файле отсутствует ключ 'messages'.")
        return

    # Перебираем все сообщения в списке
    for message in data['messages']:
        # Нас интересуют только обычные сообщения, а не служебные (про вступление в чат, закреп и т.д.)
        if message.get('type') == 'message':
            # Безопасно получаем имя отправителя
            sender = message.get('from', 'Неизвестный отправитель')
            
            # Обрабатываем текст, который может быть строкой или списком
            raw_text = message.get('text', '')
            
            full_text = ''
            if isinstance(raw_text, str):
                full_text = raw_text
            elif isinstance(raw_text, list):
                # Собираем текст из частей, если он разбит на форматированные куски
                for part in raw_text:
                    if isinstance(part, str):
                        full_text += part
                    elif isinstance(part, dict) and 'text' in part:
                        full_text += part['text']
            
            # Добавляем в результат, только если есть и отправитель, и текст
            if sender and full_text.strip():
                cleaned_messages.append({
                    'sender': sender,
                    'text': full_text
                })

    # Сохраняем очищенный список в новый JSON-файл
    with open(output_file, 'w', encoding='utf-8') as f:
        # ensure_ascii=False для корректного отображения кириллицы
        # indent=2 для красивого форматирования файла
        json.dump(cleaned_messages, f, ensure_ascii=False, indent=2)

    print(f"Готово! Обработано {len(cleaned_messages)} сообщений.")
    print(f"Результат сохранен в файл '{output_file}'.")


# Запускаем парсер
if __name__ == "__main__":
    parse_chat_history(input_filename, output_filename)