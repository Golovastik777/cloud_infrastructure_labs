# NeoShop — облачная инфраструктура (курс по облачным сетям)

Учебный проект: проектирование облачной инфраструктуры для интернет-магазина «NeoShop» — витрина, REST API, поиск, PostgreSQL и Redis, развёрнутые в VPC `10.20.0.0/16` на три зоны доступности с балансировкой через ALB, зональными NAT Gateway и гибридной связностью с on-premise ДЦ (Direct Connect + Site-to-Site VPN).


## Автор

- Яковлев Игорь — GitHub `@rafstonovich`


## Лабораторные работы

| № | Тема | Материалы |
| --- | --- | --- |
| 1 | Сетевая архитектура облака: VPC, балансировщики, связность | [`report.md`](report.md), [`scheme/vpc.png`](scheme/vpc.png) |
| 2 | Полный мониторинг API-бэкенда: метрики, логи, трейсы, алерты | [`../lab-2/README.md`](../lab-2/README.md), раздел «Лабораторная работа 2» в [`report.md`](report.md) |

## Структура

```
marketgrad-cloud/
├── README.md      
├── report.md       
└── scheme/
    ├── vpc.png      
    └── vpc.svg      
```

