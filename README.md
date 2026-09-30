# NeoShop — облачная инфраструктура (курс по облачным сетям)

Учебный проект: проектирование облачной инфраструктуры для интернет-магазина «NeoShop» — витрина, REST API, поиск, PostgreSQL и Redis, развёрнутые в VPC `10.20.0.0/16` на три зоны доступности с балансировкой через ALB, зональными NAT Gateway и гибридной связностью с on-premise ДЦ (Direct Connect + Site-to-Site VPN).


## Автор

- Яковлев Игорь — GitHub `@rafstonovich`


## Лабораторные работы

| № | Тема | Материалы |
| --- | --- | --- |
| 1 | Сетевая архитектура облака: VPC, балансировщики, связность | [`lab1/report.md`](lab1/report.md), [`lab1/scheme/vpc.png`](lab1/scheme/vpc.png) |
| 2 | Полный мониторинг API-бэкенда: метрики, логи, трейсы, алерты | [`lab-2/README.md`](lab-2/README.md), раздел «Лабораторная работа 2» в [`lab1/report.md`](lab1/report.md) |

## Структура

```
cloud_infrastructure_labs/
├── README.md              # этот файл: проект, автор, список лаб
├── lab1/
│   ├── AGENTS.md
│   ├── report.md          # сквозной отчёт: раздел на каждую лабу
│   └── scheme/
│       ├── vpc.png
│       └── vpc.svg
└── lab-2/
    ├── README.md          # запуск стенда мониторинга, метрики, алерты
    ├── docker-compose.yml
    ├── app/               # заглушка NeoShop API
    ├── alert-receiver/
    ├── configs/
    └── screenshots/
```

