<!-- confluence-page-id: 1966098 -->

If you are a user who wants to publish pages to Confluence, you should install the package [markdown-to-confluence](https://pypi.org/project/markdown-to-confluence/) from PyPI. If you are a developer who wants to contribute, you should clone the repository [md2conf](https://github.com/hunyadi/md2conf) from GitHub.

This document illustrates the [code snippet element](https://support.atlassian.com/confluence-cloud/docs/insert-elements-into-a-page/#Code-snippet) support in Confluence for various languages. The list of languages is not exhaustive.

A language-neutral code block:

```
func:
    preformatted text
```

C:

```c
#include <stdio.h>

int main(void)
{
    printf("hello, world\n");
}
```

C++:

```cpp
#include <iostream>

int main()
{
    std::cout << "Hello World" << std::endl;
    return 0;
}
```

C#:

```csharp
class Program
{
    static void Main()
    {
        System.Console.WriteLine("Hello World");
    }
}
```

CSS:

```css
body {
    background: #000 url(images/bg.gif) no-repeat left top;
    font-family: sans-serif;
}
h1 {
    font-weight: bold;
}
```

Go:

```go
package main
import "fmt"
func main() {
    fmt.Println("hello world")
}
```

HTML:

```html
<html>
    <title>An HTML document</title>
    <body>
        <p>This <i>is</i> an <b>HTML</b> document.</p>
    </body>
</html>
```

Java:

```java
class Simple {
    public static void main(String args[]) {
        System.out.println("Hello Java!");
    }
}
```

JavaScript:

```javascript
alert('Hello World');
```

JSON:

```json
{
    "boolean": true,
    "integer": 42,
    "string": "value",
    "list": [1,2,3]
}
```

Kotlin:

```kotlin
fun main() {
    val scope = "World"
    println("Hello, $scope!")
}

fun main(args: Array<String>) {
    for (arg in args)
        println(arg)
}
```

Objective-C:

```objectivec
#import <Foundation/Foundation.h>

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        NSLog(@"Hello, World!");
    }
    return 0;
}
```

PHP:

```php
<?= "Hello world\n" ?>
```

Python:

```python
def func(n: int) -> str:
    return str(n)
```

Ruby:

```ruby
class MegaGreeter
  attr_accessor :names

  def initialize(names = "World")
    @names = names
  end
```

Rust:

```rust
fn main() {
    // Print text to the console.
    println!("Hello World!");
}
```

Scala:

```scala
object HelloWorld extends App {
   println("Hello World")
}
```

Swift:

```swift
class Shape {
    var numberOfSides = 0
    func simpleDescription() -> String {
        return "A shape with \(numberOfSides) sides."
    }
}
```

TeX:

```tex
\title{A  short \LaTeX Template}
\date{\today}

\documentclass[12pt]{article}

\begin{document}
\maketitle

\section{Introduction}
Correct and improve the following examples of technical writing.
\begin{enumerate}
\item For $n>2\  f(n)=(na+n^2)/(n-1).\ f(2)=2a+4$ for example.\\
\item $a$ is negative so by (1.1)\ $a^2>a$.
\end{enumerate}

\end{document}
```

YAML:

```yaml
--- # The Smiths
- {name: John Smith, age: 33}
- name: Mary Smith
  age: 27
- [name, age]: [Rae Smith, 4]   # sequences as keys are supported
--- # People, by gender
men: [John Smith, Bill Jones]
women:
  - Mary Smith
  - Susan Williams
```
