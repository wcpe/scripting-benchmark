total = 0
for i in 0..<__ITER__ {
 value = &numbers.get(&i % 128)
 if &value % 3 == 0 {
  total += (&value * 2)
 } else {
  total -= &value
 }
}
&total
