var total = 0
for (i in 0 until __ITER__) {
    val value = numbers.get(i % 128) as Int
    if (value % 3 == 0) {
        total += value * 2
    } else {
        total -= value
    }
}
total
