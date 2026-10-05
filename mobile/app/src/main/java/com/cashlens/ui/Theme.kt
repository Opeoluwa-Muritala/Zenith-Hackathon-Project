package com.cashlens.ui
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
private val Light=lightColorScheme(primary=Color(0xFF075E54),secondary=Color(0xFFE6A700),error=Color(0xFFB3261E),surface=Color(0xFFF7F9F8))
private val Dark=darkColorScheme(primary=Color(0xFF75D7C8),secondary=Color(0xFFFFC94A),error=Color(0xFFFFB4AB))
@Composable fun CashlensTheme(dark:Boolean=false,content:@Composable()->Unit)=MaterialTheme(colorScheme=if(dark) Dark else Light,content=content)
