# GitLab CI/CD Component Templates — Examples

> Эти YAML-файлы — **примеры/историческая справка**, они **не используются**
> приложением и не заливаются в GitLab на этапе provisioning.

## Что это

Ранее provisioning GitLab CI/CD Components и пайплайнов выполнялся снаружи
приложения (bash-скрипт `provision-gitlab.sh` и Terraform). Эти шесть файлов
были единственным источником содержимого компонентов, который читался с диска
при заливке в проект `bigbug-mirrors/components`.

Теперь создание GitLab-проектов (components/pipelines), компонентов и
пайплайнов выполняется самим приложением через API:

- `POST /api/gitlab-projects` — создание/импорт проектов (components | pipelines);
- `POST /api/components/presets` (GET) — список встроенных пресетов компонентов;
- `POST /api/components/{id}/push` — заливка содержимого компонента;
- `POST /api/pipelines/configs/{id}/push-ci` — генерация и заливка `.gitlab-ci.yml`.

## Где живут реальные пресеты

Реальные (рабочие) пресеты вшиты в код как константы:

[`backend/app/services/gitlab_projects/presets.py`](../../../backend/app/services/gitlab_projects/presets.py)

Их YAML-содержимое идентично файлам в этом каталоге, но хранится в коде,
чтобы runtime provisioning никогда не читал файлы с диска.

## Файлы

| Файл | Назначение (историческое) |
|------|---------------------------|
| `docker-hub-to-harbor-template.yml` | Копирование образов Docker Hub → Harbor (crane) |
| `gold-image-template.yml` | Сборка Gold (base) образов + cosign + notify |
| `app-image-template.yml` | Сборка App образов на gold-базе + cosign + notify |
| `mirror-template.yml` | Синхронизация зеркал GitHub → GitLab |
| `docker-sync-template.yml` | Синхронизация Docker-тегов + notify |
| `helm-sync-template.yml` | Синхронизация Helm-чартов + notify |
