---
title: "PlantUML Diagrams"
---

If you are a user who wants to publish pages to Confluence, you should install the package [markdown-to-confluence](https://pypi.org/project/markdown-to-confluence/) from PyPI. If you are a developer who wants to contribute, you should clone the repository [md2conf](https://github.com/hunyadi/md2conf) from GitHub.

[PlantUML](https://plantuml.com/) is an open-source tool that allows you to create diagrams from a plain text language. You can include PlantUML diagrams in your documents to create visual representations of systems, processes, and relationships.

## Sequence Diagram

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

## Class Diagram

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

## Component Diagram

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
