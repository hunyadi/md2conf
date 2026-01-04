---
title: "PlantUML Diagrams"
---

<!-- confluence-page-id: 00000000000 -->

[PlantUML](https://plantuml.com/) is an open-source utility that facilitates the rapid creation of a wide array of diagrams using plain text.

You can include PlantUML diagrams in your documents to create visual representations of systems, processes, and relationships.

## Class diagrams

Class diagrams visualize the structure of a system by showing its classes, attributes, methods, and relationships. They are essential for object-oriented design.

```plantuml
@startuml
abstract class Animal {
  +name: String
  +age: int
  +makeSound(): void
}

class Dog {
  +breed: String
  +bark(): void
  +makeSound(): void
}

class Cat {
  +color: String
  +meow(): void
  +makeSound(): void
}

Animal <|-- Dog
Animal <|-- Cat
@enduml
```

## Sequence diagrams

Sequence diagrams show how objects interact with each other over time. They are useful for modeling the dynamic behavior of a system and understanding message flows between components.

```plantuml
@startuml
actor User
participant "Web App" as Web
participant "API Server" as API
database "Database" as DB

User -> Web: Login request
Web -> API: Authenticate(username, password)
API -> DB: Query user
DB --> API: User data
API --> Web: Auth token
Web --> User: Login successful
@enduml
```

## Component diagrams

Component diagrams illustrate the organization and dependencies among software components, helping to visualize system architecture.

```plantuml
@startuml
package "Frontend" {
  [React App] as React
  [State Manager] as Redux
}

package "Backend" {
  [REST API] as API
  [Business Logic] as Logic
  [Data Access] as DAO
}

database "PostgreSQL" as DB

React --> Redux
React --> API
API --> Logic
Logic --> DAO
DAO --> DB
@enduml
```

## Use case diagrams

Use case diagrams show the interactions between actors and use cases in a system. They are used to capture functional requirements of a system.

```plantuml
@startuml
:User: --> (Login)
:User: --> (Browse Products)
:Admin: --> (Manage Inventory)
(Manage Inventory) ..> (Browse Products) : includes
@enduml
```
