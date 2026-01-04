void print(const char *data);
void printNumber(int number);

extern double _sin(double);
extern double _sqrt(double);

void test(){
    print("Just for good measure - sqrt(2) * 100 is:");
    float result = _sqrt(2);
    result *= 100.f;
    printNumber(result);

    print("And now... what's sin(45deg?) * 100:");
    printNumber(_sin(3.1415 / 4.) * 100.);
}
