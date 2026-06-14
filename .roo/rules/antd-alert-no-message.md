# Ant Design Alert: ЗАПРЕТ `message`, использовать `title`

## Жёсткое правило

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать проп `message` в компоненте `<Alert>` из Ant Design.**

Проп `message` является устаревшим (deprecated) в Ant Design v5+. Вместо него необходимо использовать проп **`title`**.

## Неправильно ❌

```tsx
<Alert
  type="error"
  message="Failed to load mirrors"                    // ❌ ЗАПРЕЩЕНО
  description="Please try again later."
  showIcon
/>
```

## Правильно ✅

```tsx
<Alert
  type="error"
  title="Failed to load mirrors"                      // ✅ ПРАВИЛЬНО
  description="Please try again later."
  showIcon
/>
```

## Примечание

Это правило не относится к компоненту `message` из `antd` (например, `message.success()`, `message.error()`) — там `message` это вызов API, а не проп Alert.
