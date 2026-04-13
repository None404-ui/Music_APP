#include <iostream>
#include <string>
#include <sstream>
#include <cctype>
#include <sys/types.h>
#include <unistd.h>
#include <sys/wait.h>
#include <cmath>
#include <cstring>

using namespace std;

struct Payload {
    double x;
    double y;
};

int pipe_to_srv[2];
int pipe_to_cli[2];
pid_t child_pid;

void help() {
    cout << "Справка:\n"
         << "ID: вариант 26\n"
         << "f(x,y)=sum_{n=0}^{500}(sin(x^n)+tg(y))/(n+x)!\n"
         << "x и y задаются в радианах (как в sin и tg из cmath).\n"
         << "Запуск без аргументов — ввод x и y с клавиатуры.\n"
         << "--help — показать справку и выйти.\n";
}

static string trim_spaces(const string& s) {
    size_t a = 0;
    while (a < s.size() && isspace(static_cast<unsigned char>(s[a])))
        ++a;
    size_t b = s.size();
    while (b > a && isspace(static_cast<unsigned char>(s[b - 1])))
        --b;
    return s.substr(a, b - a);
}

double read_double(const string& msg) {
    for (;;) {
        cout << msg;
        string line;
        if (!getline(cin, line))
            return 0.0;
        line = trim_spaces(line);
        if (line.empty()) {
            cout << "Ошибка ввода, повторите\n";
            continue;
        }
        istringstream iss(line);
        double v;
        iss >> v;
        if (iss.fail()) {
            cout << "Ошибка ввода, повторите\n";
            continue;
        }
        iss >> ws;
        if (!iss.eof()) {
            cout << "Ошибка ввода, повторите\n";
            continue;
        }
        if (!isfinite(v)) {
            cout << "Ошибка ввода, повторите\n";
            continue;
        }
        return v;
    }
}

double f(double x, double y) {
    const double ty = tan(y);
    double acc = 0.0;
    for (int n = 0; n <= 500; ++n) {
        const double den = tgamma(static_cast<double>(n) + x + 1.0);
        acc += (sin(pow(x, static_cast<double>(n))) + ty) / den;
    }
    return acc;
}

int main(int argc, char* argv[]) {
    if (argc > 1 && strcmp(argv[1], "--help") == 0) {
        help();
        return 0;
    }
    if (pipe(pipe_to_srv) == -1 || pipe(pipe_to_cli) == -1) {
        cerr << "pipe error\n";
        return 1;
    }
    child_pid = fork();
    if (child_pid == -1) {
        cerr << "fork error\n";
        return 1;
    }
    if (child_pid == 0) {
        close(pipe_to_srv[1]);
        close(pipe_to_cli[0]);
        Payload p;
        ssize_t r = read(pipe_to_srv[0], &p, sizeof(Payload));
        close(pipe_to_srv[0]);
        if (r != static_cast<ssize_t>(sizeof(Payload))) {
            close(pipe_to_cli[1]);
            _exit(1);
        }
        double res = f(p.x, p.y);
        write(pipe_to_cli[1], &res, sizeof(double));
        close(pipe_to_cli[1]);
        _exit(0);
    }
    close(pipe_to_srv[0]);
    close(pipe_to_cli[1]);
    double x = read_double("x (радианы): ");
    double y = read_double("y (радианы): ");
    Payload p{x, y};
    if (write(pipe_to_srv[1], &p, sizeof(Payload)) != static_cast<ssize_t>(sizeof(Payload))) {
        close(pipe_to_srv[1]);
        waitpid(child_pid, nullptr, 0);
        return 1;
    }
    close(pipe_to_srv[1]);
    double out = 0.0;
    ssize_t rr = read(pipe_to_cli[0], &out, sizeof(double));
    close(pipe_to_cli[0]);
    if (rr != static_cast<ssize_t>(sizeof(double))) {
        waitpid(child_pid, nullptr, 0);
        return 1;
    }
    waitpid(child_pid, nullptr, 0);
    cout << "Результат: " << out << "\n";
    return 0;
}
