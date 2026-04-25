var sum = 0;
for (var i = 0; i < __ITER__; i++) {
    var point = new java.awt.Point(i, i + 1);
    sum += point.x + point.y;
}
sum;
