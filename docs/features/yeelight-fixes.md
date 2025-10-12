# Исправление ошибки валидации порта Yeelight

## Проблема
При добавлении устройства Yeelight через веб-интерфейс возникала ошибка:
```
ValueError: invalid literal for int() with base 10: ''
```

### Причина
1. Поле `port` в форме имеет `"advanced": true` и `"default": 55443`
2. Когда пользователь не раскрывает расширенные настройки, frontend отправлял пустую строку `""` вместо значения по умолчанию
3. Backend (`validate.py`) пытался напрямую преобразовать это значение: `int("")` → ошибка

## Решение

### 1. Frontend (FlowSetupForm.tsx)

#### Добавлена функция `applyFormDefaults()`
Автоматически применяет значения по умолчанию для полей формы, которые не были заполнены:
- Проверяет каждое поле из схемы
- Если значение пустое и есть default → использует default
- Для числовых полей правильно преобразует строки в числа

#### Обновлен context
Теперь context использует обогащенные данные формы с применёнными default значениями для всех form steps.

#### Улучшена обработка числовых полей
- Используется правильный `<Input type="number">`
- Добавлены атрибуты `min`, `max`, `step`
- Значения правильно преобразуются в числа при вводе
- Показывается placeholder с default значением
- Добавлена поддержка описаний для полей

### 2. Backend (validate.py)

Добавлена защита от некорректных значений порта:
```python
port_value = payload.get("port", 55443)
if port_value == "" or port_value is None:
    port = 55443
else:
    try:
        port = int(port_value)
    except (ValueError, TypeError):
        port = 55443
```

## Результат
- ✅ Пустые строки для числовых полей обрабатываются корректно
- ✅ Default значения автоматически применяются для скрытых advanced полей
- ✅ Числовые поля отображаются с правильным типом input
- ✅ Backend защищён от некорректных значений
- ✅ Устройства Yeelight теперь можно добавлять без ошибок

## Тестирование
```bash
# Проверить логику парсинга порта
python3 test_port_parsing.py

# Собрать frontend
cd web/frontend && npm run build
```

## Затронутые файлы
- `web/frontend/src/components/integrations/FlowSetupForm.tsx`
- `connectors/yeelight/actions/validate.py`
