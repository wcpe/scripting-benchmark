sum = 0
for i in 0..<__ITER__ {
 point = new java.awt.Point(&i, &i + 1)
 sum += &point.x + &point.y
}
&sum
