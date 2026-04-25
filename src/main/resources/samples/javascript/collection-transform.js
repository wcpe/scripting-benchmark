var total = 0;
for (var i = 0; i < __ITER__; i++) {
    var value = numbers.get(i % 128);
    if (value % 3 === 0) {
        total += value * 2;
    } else {
        total -= value;
    }
}
total;
