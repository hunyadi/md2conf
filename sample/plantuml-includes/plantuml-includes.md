---
title: "PlantUML with Includes and Themes"
---

This document demonstrates PlantUML diagrams using includes and themes.

## Diagram with Include

This diagram uses a common include file to share styling and definitions:

```plantuml
@startuml
!include common.puml

Alice -> Bob: Hello
Bob -> Alice: Hi!
@enduml
```

## Diagram with Custom Styling

```plantuml
@startuml
!include common.puml

participant User
participant System
database DB

User -> System: Request
System -> DB: Query
DB --> System: Result
System --> User: Response
@enduml
```
