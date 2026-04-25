hits = 0
for i in 0..<__ITER__ {
 matcher = &pattern.matcher(&regexText)
 if &matcher.find() {
  hits += &matcher.group(1).length() + &matcher.group(2).length()
 }
}
&hits
