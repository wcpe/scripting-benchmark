var sum = 0;
for (var i = 0; i < __ITER__; i++) {
    sum += lookupMap.get('k' + (i % 128));
}
sum;
