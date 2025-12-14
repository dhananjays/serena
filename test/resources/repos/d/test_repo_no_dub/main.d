import std.stdio;

void main()
{
    writeln("Hello from non-DUB D project!");
    testFunction();
}

void testFunction()
{
    writeln("Test function called");
}

struct SimpleStruct
{
    int value;

    void display()
    {
        writefln("Value: %d", value);
    }
}
