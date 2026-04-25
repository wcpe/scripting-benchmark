var sum = 0
for (i in 0 until __ITER__) {
    val point = java.awt.Point(i, i + 1)
    sum += point.x + point.y
}
sum
