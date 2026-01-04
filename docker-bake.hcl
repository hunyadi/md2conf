group "default" {
  targets = ["base", "mermaid", "plantuml", "all"]
}

target "base" {
  context = "."
  dockerfile = "Dockerfile"
  target = "base"
  tags = ["md2conf:base"]
}

target "mermaid" {
  context = "."
  dockerfile = "Dockerfile"
  target = "mermaid"
  tags = ["md2conf:mermaid"]
}

target "plantuml" {
  context = "."
  dockerfile = "Dockerfile"
  target = "plantuml"
  tags = ["md2conf:plantuml"]
}

target "all" {
  context = "."
  dockerfile = "Dockerfile"
  target = "all"
  tags = ["md2conf:all"]
}
