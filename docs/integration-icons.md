# Добавление иконок для интеграций

## Обзор

Каждая интеграция в IoT2MQTT может иметь собственную иконку, которая отображается в веб-интерфейсе. Это улучшает пользовательский опыт и помогает быстро идентифицировать интеграции.

## Как добавить иконку

### 1. Создайте или получите иконку

Иконка должна быть в формате SVG для лучшего масштабирования и производительности.

**Опции:**
- Скачайте логотип бренда с официального сайта
- Используйте фавикон сайта производителя
- Создайте собственную SVG иконку

### 2. Разместите файл icon.svg

Поместите файл `icon.svg` в директорию вашей интеграции:

```
connectors/
  └── your_integration/
      ├── manifest.json
      ├── setup.json
      ├── connector.py
      └── icon.svg          ← Здесь!
```

### 3. Форматы иконок

#### SVG с встроенным PNG (рекомендуется для небольших изображений)

Если у вас есть PNG логотип, вы можете встроить его в SVG:

```bash
# Конвертируйте PNG в base64
base64 -w 0 logo.png > logo_base64.txt

# Создайте SVG файл
cat > icon.svg << EOF
<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
  <image width="32" height="32" href="data:image/png;base64,$(cat logo_base64.txt)"/>
</svg>
EOF
```

#### Чистый SVG (рекомендуется)

Используйте векторный SVG для наилучшего качества:

```xml
<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
  <circle cx="16" cy="16" r="14" fill="#4285F4"/>
  <path d="M16 8v8l6 6" stroke="white" stroke-width="2"/>
</svg>
```

## Автоматическая загрузка иконки

Backend API автоматически обнаруживает и предоставляет иконку через endpoint:

```
GET /api/integrations/{integration_name}/icon
```

Веб-интерфейс автоматически загружает иконку для каждой интеграции, если файл существует.

## Fallback иконка

Если файл `icon.svg` не найден, система автоматически использует иконку по умолчанию (лампочка).

## Примеры

### Yeelight интеграция

```bash
cd connectors/yeelight

# Скачайте фавикон
curl -L "https://en.yeelight.com/favicon.ico" -o favicon.png

# Конвертируйте в SVG с base64
base64 -w 0 favicon.png > favicon_base64.txt
cat > icon.svg << EOF
<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
  <image width="32" height="32" href="data:image/png;base64,$(cat favicon_base64.txt)"/>
</svg>
EOF

# Очистите временные файлы
rm favicon.png favicon_base64.txt
```

## Рекомендации

1. **Размер**: Используйте размер 32x32 пикселей или кратный ему
2. **Формат**: SVG предпочтителен для масштабируемости
3. **Размер файла**: Старайтесь держать размер < 10 KB
4. **Цвета**: Используйте фирменные цвета бренда
5. **Простота**: Иконка должна хорошо читаться в малом размере

## Поиск логотипов брендов

Полезные ресурсы для поиска официальных логотипов:

- Официальный сайт производителя (часто в разделе "Press Kit" или "Brand Assets")
- Фавикон сайта: `https://example.com/favicon.ico`
- [Clearbit Logo API](https://clearbit.com/logo)
- [Brandfetch](https://brandfetch.com/)

## Техническая реализация

### Backend (Python/FastAPI)

```python
@router.get("/api/integrations/{name}/icon")
async def get_integration_icon(name: str):
    """Get integration icon"""
    icon_path = config_service.connectors_path / name / "icon.svg"

    if not icon_path.exists():
        # Fallback to default icon
        raise HTTPException(status_code=404, detail="Icon not found")

    return FileResponse(icon_path, media_type="image/svg+xml")
```

### Frontend (React/TypeScript)

```typescript
// BrandIcon.tsx автоматически загружает иконку
<BrandIcon
  integration="yeelight"
  className="w-10 h-10"
  size={40}
/>
```

Компонент `BrandIcon` пытается загрузить иконку через API и автоматически использует fallback при отсутствии файла.
