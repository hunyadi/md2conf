<!-- confluence-page-id: 00000000000 -->

## Mermaid

```mermaid
classDiagram
Entity <|-- Product
Entity <|-- Customer
Entity <|-- Vendor
Vendor <|-- Store
Entity <|-- Project
```

## PlantUML

```plantuml
@startuml
:User: --> (Login)
:User: --> (Browse Products)
:Admin: --> (Manage Inventory)
(Manage Inventory) ..> (Browse Products) : includes
@enduml
```
