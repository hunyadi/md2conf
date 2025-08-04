<!-- confluence-page-id: 1966098 -->

If you are a user who wants to publish pages to Confluence, you should install the package [markdown-to-confluence](https://pypi.org/project/markdown-to-confluence/) from PyPI. If you are a developer who wants to contribute, you should clone the repository [md2conf](https://github.com/hunyadi/md2conf) from GitHub.

This document illustrates the [code snippet element](https://support.atlassian.com/confluence-cloud/docs/insert-elements-into-a-page/#Code-snippet) support in Confluence for various languages. The list of languages is not exhaustive.

A language-neutral code block:

```
func:
    preformatted text
```

ActionScript:

```actionscript3
public class HelloWorld extends Sprite {
    public function HelloWorld() {
        trace("Hello, ActionScript 3!");
    }
}
```

Ada:

```ada
with Ada.Text_IO; use Ada.Text_IO;

procedure Hello_World is
begin
    Put_Line("Hello, Ada!");
end Hello_World;
```

AutoIt:

```autoit
Func Add($a, $b)
    Return $a + $b
EndFunc

Local $result = Add(5, 3)
MsgBox(0, "Result", "5 + 3 = " & $result)
```

Bash:

```bash
#!/bin/bash

string=$1
strLength=${#string}

for ((i=$strLength-1;i>-1;i--));
do
    reverseStr+=${string:i:1}
done
echo $reverseStr
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

Clojure:

```clojure
(ns reverse-string
	(:gen-class))

(defn main [args]
  (if (not= (count args) 0)
    (println(clojure.string/reverse (first args)))
  ))

(main *command-line-args*)
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

Delphi:

```delphi
program HelloWorld;

uses
  SysUtils;

begin
  Writeln('Hello, Delphi!');
end.
```

Diff:

```diff
- console.log("Goodbye, world!");
+ console.log("Hello, world!");
```

Erlang:

```erlang
-module(hello).
-export([start/0]).

start() ->
    io:format("Hello, Erlang!~n"),
    spawn(fun() -> io:format("From a new process!~n") end).
```

Fortran:

```fortran
program reversestring
character(len=100) :: argument
character(len=:), allocatable :: buff, reversed
integer :: i, n
call GET_COMMAND_ARGUMENT(1,argument)
allocate (buff, mold=argument)
n = len(argument)
do i = 0, n - 1
    buff(n-i : n-i) = argument(i+1 : i+1)
end do
reversed = adjustl(trim(buff))
write(*,'(g0.8)')reversed
end program reversestring
```

Go:

```go
package main
import "fmt"
func main() {
    fmt.Println("hello world")
}
```

GraphQL:

```graphql
query {
  user(id: "123") {
    id
    name
    email
    posts {
      title
      published
    }
  }
}
```

Haskell:

```haskell
square :: Int -> Int
square x = x * x

main :: IO ()
main = do
    putStrLn "Hello, Haskell!"
    print (square 5)
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

Julia:

```julia
function greet(name="Julia")
    println("Hello, $name!")
end

greet()
greet("World")

square(x) = x^2
println("Square of 5 is ", square(5))
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

Lua:

```lua
function fib(n)
  local a, b = 0, 1
  for k = 1, n do
    a, b = b, a + b
    print(k .. ": " .. a)
  end
end
```

Mathematica:

```mathematica
(* Define a function and evaluate it *)
f[x_] := x^2 + 3 x + 2
f[5]

(* Plot the function *)
Plot[f[x], {x, -5, 5}]
```

MATLAB:

```matlab
function greet(name)
    fprintf('Hello, %s!\n', name);
end

greet('User');

disp(['3^2 = ', num2str(3^2)])
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

Octave:

```octave
function y = square(x)
  y = x^2;
endfunction

disp("Hello, Octave!")

a = 4;
disp(["Square of ", num2str(a), " is ", num2str(square(a))])
```

Perl:

```perl
use strict;
use warnings;

sub greet {
    my $name = shift;
    return "Hello, $name!";
}

print greet("Perl"), "\n";
```

PHP:

```php
<?= "Hello world\n" ?>
```

PowerShell:

```powershell
function Get-Rot13([string]$Str) {
    # -regex is case-insensitive
    $Result = switch -regex ($Str.ToCharArray()) {
        "[a-m]" { [char]([byte]$_ + 13) } # A-M, a-m -> N-Z, n-z
        "[n-z]" { [char]([byte]$_ - 13) } # N-Z, n-z -> A-M, a-m
        default { $_ } # Else, don't change
    }
    -join $Result
}
```

Prolog:

```prolog
:- initialization(main).
main():-
    write("Hello, World!\n"),
    halt.
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

Scheme:

```scheme
(define (reverse-string x)
  (list->string (reverse (string->list x))))

(if (> (length (command-line)) 1)
  (display (reverse-string (list-ref (command-line) 1)))
)
```

Smalltalk:

```smalltalk
-10 to: 10 do: [ :i |
  numSpaces := i abs.
  numSpaces timesRepeat: [ ' ' display ].
  (21 - (2 * numSpaces)) timesRepeat: [ '*' display ].
  Character nl display.
]
```

SQL:

```sql
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100)
);

INSERT INTO users VALUES (1, 'Alice', 'alice@example.com');

SELECT name FROM users WHERE id = 1;
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

TypeScript:

```typescript
let myString: string = (process.argv.length >= 3) ? process.argv[2] : "";

const reverse = (str: string) => str.split("").reverse().join("");
```

Visual Basic:

```vb
Public Sub Main()
    System.Console.WriteLine("Hello, World!")
End Sub
```

Verilog:

```verilog
module main;
  initial
    begin
      $display("Hello, World!");
      $finish(0);
    end
endmodule
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
