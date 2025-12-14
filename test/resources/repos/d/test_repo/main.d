import std.stdio;

void main()
{
    writeln("Hello, D!");
    Helper();
}

void Helper()
{
    writeln("Helper function called");
}

struct DemoStruct
{
    int field;

    void greet()
    {
        writeln("Greetings from DemoStruct");
    }
}

class DemoClass
{
    private string name;

    this(string name)
    {
        this.name = name;
    }

    void sayHello()
    {
        writefln("Hello from %s", name);
    }
}

void UsingHelper()
{
    Helper();
}

int calculate(int a, int b)
{
    return a + b;
}
