<!-- confluence-page-id: 00000000000 -->

## Inside Details/Summary block

<!-- If you add the attribute of markdown it'll be converted to html -->
<div markdown="1">
<summary><b>My summary</b></summary>

| Operation  | Types | Subtypes | Additional info |
|------------|-------|----------|-----------------|
| Test       | One   | Sub-One  | This is a test  |
</div>

<!-- With no attribute it will not be converted and you'll end up with the raw markdown table -->
<div>
## Outside of details/summary block

| Operation  | Types | Subtypes | Additional info |
|------------|-------|----------|-----------------|
| Test2      | Two   | Sub-Two  | This is a test2 |
</div>
