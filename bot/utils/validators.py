import re


def is_valid_name(name: str) -> bool:
    """
    Проверяет, что имя состоит из букв, пробелов, дефисов и апострофов,
    и имеет длину от 2 до 30 символов. Поддерживает кириллицу и латиницу.
    
    Args:
        name: Имя для проверки
        
    Returns:
        True если имя валидно, иначе False
    """
    if not name or not isinstance(name, str):
        return False
    
    pattern = r"^[а-яёА-ЯЁa-zA-Z\s\-']{2,30}$"
    return bool(re.match(pattern, name.strip()))


def is_valid_city(city: str) -> bool:
    """
    Проверяет, что название города имеет длину от 2 до 50 символов.
    
    Args:
        city: Название города для проверки
        
    Returns:
        True если название валидно, иначе False
    """
    if not city or not isinstance(city, str):
        return False
    
    return 2 <= len(city.strip()) <= 50