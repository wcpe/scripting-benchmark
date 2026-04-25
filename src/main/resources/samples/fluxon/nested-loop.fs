total = 0
for i in 0..<__ITER__ {
 for j in 0..<64 {
  total += (&i * &j) % 7
 }
}
&total
