#include <stdio.h>

int main(void)
{
	float number;
	int base;
	if (!scanf("%f %d", &number, &base))
	{
		printf("Fehlerhafte Eingabe!\n");
		return 1;
	}

	printf("%f %d", number, base);
	return 0;
}
