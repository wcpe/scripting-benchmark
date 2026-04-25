var total = 0
for (i in 0 until __ITER__) {
    val value = numbers[i % 128]
    if (value % 3 == 0) {
        total += value * 2
    } else {
        total -= value
    }
}
total
